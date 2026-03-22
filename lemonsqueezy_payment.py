"""
LemonSqueezy payment integration for Tainment+ subscriptions.

Flow:
1. User runs t!upgrade <tier>
2. Bot creates a LemonSqueezy checkout (custom price, embeds Discord user ID)
3. Bot sends the checkout URL to the user via DM
4. User completes payment on LemonSqueezy's hosted page
5. Background task polls orders every 2 minutes to detect completed payments
6. Bot upgrades the user's subscription automatically

Setup:
1. Create a free account at lemonsqueezy.com (no business registration needed)
2. Create a Store, then a Product with one Variant (any price — we override it)
3. Add to .env:
   LEMONSQUEEZY_API_KEY=your_api_key
   LEMONSQUEEZY_STORE_ID=your_store_id
   LEMONSQUEEZY_VARIANT_ID=your_variant_id
   LEMONSQUEEZY_WEBHOOK_SECRET=optional_for_instant_fulfillment
"""

import discord
from discord.ext import commands, tasks
import aiohttp
import os
import hmac
import hashlib
import json
import logging
import aiosqlite
from datetime import datetime, timezone, timedelta
import asyncio
import config
import database as db

logger = logging.getLogger('tainment.lemonsqueezy')

LS_API_BASE = 'https://api.lemonsqueezy.com/v1'
DISCOUNTS = {1: 0, 3: 0.10, 6: 0.15, 12: 0.20}
SERVER_MEMBER_DISCOUNT = 0.30  # 30% off for members of Basic/Pro server subscribers


def _get_env(key: str) -> str:
    return os.getenv(key, '')


def calculate_price(tier: str, months: int) -> float:
    base = config.SUBSCRIPTION_TIERS[tier]['price']
    discount = DISCOUNTS.get(months, 0)
    return round(base * months * (1 - discount), 2)


async def _ls_request(method: str, path: str, api_key: str, **kwargs):
    """Make an authenticated LemonSqueezy API request."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/vnd.api+json',
        'Content-Type': 'application/vnd.api+json',
    }
    async with aiohttp.ClientSession() as session:
        async with session.request(method, f'{LS_API_BASE}{path}', headers=headers, **kwargs) as resp:
            data = await resp.json(content_type=None)
            return resp.status, data


# ── Database helpers ──────────────────────────────────────────────────────────

async def init_ls_table():
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ls_checkouts (
                checkout_id  TEXT PRIMARY KEY,
                user_id      INTEGER,
                tier         TEXT,
                months       INTEGER,
                amount       REAL,
                status       TEXT DEFAULT 'pending',
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        await conn.commit()


async def _store_checkout(checkout_id: str, user_id: int, tier: str, months: int, amount: float):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO ls_checkouts (checkout_id, user_id, tier, months, amount) VALUES (?,?,?,?,?)",
            (checkout_id, user_id, tier, months, amount),
        )
        await conn.commit()


async def _get_pending():
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM ls_checkouts WHERE status='pending'") as cur:
            return await cur.fetchall()


async def _complete_checkout(checkout_id: str):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute(
            "UPDATE ls_checkouts SET status='completed', completed_at=datetime('now') WHERE checkout_id=?",
            (checkout_id,),
        )
        await conn.commit()


async def _expire_old():
    """Expire checkouts older than 2 hours."""
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute(
            "UPDATE ls_checkouts SET status='expired' WHERE status='pending' "
            "AND created_at < datetime('now', '-2 hours')",
        )
        await conn.commit()


# ── Cog ───────────────────────────────────────────────────────────────────────

class LemonSqueezyPayment(commands.Cog, name='LemonSqueezyPayment'):
    """LemonSqueezy payment processing for subscriptions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key    = _get_env('LEMONSQUEEZY_API_KEY')
        self.store_id   = _get_env('LEMONSQUEEZY_STORE_ID')
        self.variant_id = _get_env('LEMONSQUEEZY_VARIANT_ID')
        self.webhook_secret = _get_env('LEMONSQUEEZY_WEBHOOK_SECRET')

        if self.is_configured():
            self.poll_orders.start()
            logger.info('LemonSqueezy integration enabled.')
        else:
            logger.warning('LemonSqueezy env vars not set. Payments will use simulated checkout.')

    def cog_unload(self):
        if self.is_configured():
            self.poll_orders.cancel()

    def is_configured(self) -> bool:
        return bool(self.api_key and self.store_id and self.variant_id)

    # ── Polling ───────────────────────────────────────────────────────────────

    @tasks.loop(minutes=2)
    async def poll_orders(self):
        """Fetch recent paid orders and fulfill any pending checkouts."""
        await _expire_old()
        pending = await _get_pending()
        if not pending:
            return

        # Build lookup: discord_user_id (str) -> checkout row
        pending_map = {str(row['user_id']): row for row in pending}

        try:
            status, data = await _ls_request(
                'GET',
                f'/orders?filter[store_id]={self.store_id}&sort=-created_at&page[size]=50',
                self.api_key,
            )
            if status != 200:
                logger.warning(f'LemonSqueezy orders poll returned {status}')
                return

            for order in data.get('data', []):
                attrs = order.get('attributes', {})
                if attrs.get('status') != 'paid':
                    continue

                custom = attrs.get('first_order_item', {}).get('custom_data') or {}
                # custom_data is also sometimes at the top-level meta
                if not custom:
                    custom = order.get('meta', {}).get('custom_data') or {}

                uid_str = str(custom.get('discord_user_id', ''))
                if uid_str not in pending_map:
                    continue

                row = pending_map[uid_str]
                await self._fulfill(row)
                await _complete_checkout(row['checkout_id'])
                del pending_map[uid_str]

        except Exception as e:
            logger.error(f'Error polling LemonSqueezy orders: {e}', exc_info=True)

    @poll_orders.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

    # ── Fulfillment ───────────────────────────────────────────────────────────

    async def _fulfill(self, row):
        user_id = row['user_id']
        tier    = row['tier']
        months  = row['months']
        amount  = row['amount']

        old_tier = await db.get_tier(user_id)
        now = datetime.now(timezone.utc)
        sub = await db.get_subscription(user_id)

        if sub and sub['end_date']:
            existing_end = datetime.fromisoformat(sub['end_date']).replace(tzinfo=timezone.utc)
            start = max(existing_end, now)
        else:
            start = now

        end_date  = start + timedelta(days=months * 30)
        grace_end = end_date + timedelta(days=3)

        await db.update_subscription(user_id, tier, end_date.isoformat(), grace_end.isoformat())
        await db.log_subscription_change(user_id, old_tier, tier, reason=f'LemonSqueezy payment {row["checkout_id"]}')
        await db.record_payment(user_id, row['checkout_id'], amount, tier, months, 'completed')

        ts = int(end_date.timestamp())
        try:
            user = await self.bot.fetch_user(user_id)
            embed = discord.Embed(
                title='Payment Confirmed!',
                description=(
                    f'Your **{tier}** subscription is now active!\n\n'
                    f'Duration: `{months}` month{"s" if months != 1 else ""}\n'
                    f'Active until: <t:{ts}:F>\n'
                    f'Amount paid: `${amount:.2f}`'
                ),
                color=config.COLORS['success'],
            )
            embed.set_footer(text='Thank you for supporting Tainment+!')
            await user.send(embed=embed)
        except Exception:
            pass

        logger.info(f'Fulfilled {tier} x{months}mo for user {user_id}')

    # ── Checkout creation ─────────────────────────────────────────────────────

    async def create_checkout(self, ctx: commands.Context, tier: str, months: int) -> bool:
        """Create a LemonSqueezy checkout and DM the user the link. Returns True on success."""
        if not self.is_configured():
            return False

        amount       = calculate_price(tier, months)
        discount_pct = DISCOUNTS.get(months, 0)

        # Apply server member discount if the command was run in a subscribed server
        server_discount = False
        if ctx.guild:
            from server_settings import get_server_tier
            server_tier = await get_server_tier(ctx.guild.id)
            if server_tier in ('Basic', 'Pro'):
                amount = round(amount * (1 - SERVER_MEMBER_DISCOUNT), 2)
                server_discount = True

        amount_cents = int(amount * 100)

        payload = {
            'data': {
                'type': 'checkouts',
                'attributes': {
                    'custom_price': amount_cents,
                    'product_options': {
                        'name': f'Tainment+ {tier} — {months} month{"s" if months != 1 else ""}',
                        'description': (
                            f'Discord bot subscription for PopFusion.'
                            + (f' Save {int(discount_pct*100)}%!' if discount_pct else '')
                        ),
                        'redirect_url': 'https://discord.com/channels/@me',
                        'receipt_thank_you_note': 'Your Tainment+ subscription will be activated within 2 minutes.',
                    },
                    'checkout_data': {
                        'custom': {
                            'discord_user_id': str(ctx.author.id),
                            'tier': tier,
                            'months': str(months),
                        },
                    },
                    'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                },
                'relationships': {
                    'store': {
                        'data': {'type': 'stores', 'id': str(self.store_id)},
                    },
                    'variant': {
                        'data': {'type': 'variants', 'id': str(self.variant_id)},
                    },
                },
            }
        }

        try:
            status, data = await _ls_request('POST', '/checkouts', self.api_key, json=payload)

            if status not in (200, 201):
                err = data.get('errors', [{}])[0].get('detail', 'Unknown error')
                logger.error(f'LemonSqueezy checkout creation failed {status}: {err}')
                await ctx.send(embed=discord.Embed(
                    description=f'Payment system error. Please try again later.\n`{err}`',
                    color=config.COLORS['error'],
                ), ephemeral=True)
                return False

            checkout_url = data['data']['attributes']['url']
            checkout_id  = data['data']['id']
            await _store_checkout(checkout_id, ctx.author.id, tier, months, amount)

            embed = discord.Embed(
                title=f'Tainment+ {tier} Checkout',
                description=(
                    f'Click below to complete your payment securely via LemonSqueezy.\n\n'
                    f'**{tier}** — {months} month{"s" if months != 1 else ""}\n'
                    f'Total: **${amount:.2f}** USD'
                    + (f' *(Save {int(discount_pct*100)}%!)*' if discount_pct else '')
                    + (' *(+30% server member discount applied!)*' if server_discount else '') +
                    f'\n\nYour subscription activates **automatically** within 2 minutes of payment.\n'
                    f'Link expires in **1 hour**.'
                ),
                color=config.COLORS['primary'],
            )
            embed.set_footer(text='Powered by LemonSqueezy | Secure payment')

            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label='Pay with LemonSqueezy',
                url=checkout_url,
                style=discord.ButtonStyle.link,
                emoji='\U0001f34b',
            ))

            try:
                await ctx.author.send(embed=embed, view=view)
                await ctx.send(embed=discord.Embed(
                    description='Checkout link sent to your DMs!',
                    color=config.COLORS['success'],
                ), ephemeral=True)
            except discord.Forbidden:
                await ctx.send(embed=embed, view=view, ephemeral=True)

            return True

        except Exception as e:
            logger.error(f'LemonSqueezy checkout error: {e}', exc_info=True)
            await ctx.send(embed=discord.Embed(
                description='Payment system error. Please try again later.',
                color=config.COLORS['error'],
            ), ephemeral=True)
            return False

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.command(
        name='verifypayment',
        aliases=['verifypay', 'checkpay'],
        description='Manually check if your payment was processed',
    )
    async def verifypayment(self, ctx: commands.Context):
        """Force-check if your pending LemonSqueezy payment completed."""
        if not self.is_configured():
            await ctx.send(embed=discord.Embed(
                description='Payment system not configured.',
                color=config.COLORS['error'],
            ), ephemeral=True)
            return

        async with aiosqlite.connect(config.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM ls_checkouts WHERE user_id=? AND status='pending' ORDER BY created_at DESC LIMIT 1",
                (ctx.author.id,),
            ) as cur:
                row = await cur.fetchone()

        if not row:
            await ctx.send(embed=discord.Embed(
                description='No pending payment found.',
                color=config.COLORS['warning'],
            ), ephemeral=True)
            return

        await ctx.send(embed=discord.Embed(
            description='Checking your payment...', color=config.COLORS['info'],
        ), ephemeral=True)

        try:
            status, data = await _ls_request(
                'GET',
                f'/orders?filter[store_id]={self.store_id}&sort=-created_at&page[size]=100',
                self.api_key,
            )
            found = False
            if status == 200:
                uid_str = str(ctx.author.id)
                for order in data.get('data', []):
                    attrs = order.get('attributes', {})
                    if attrs.get('status') != 'paid':
                        continue
                    custom = attrs.get('first_order_item', {}).get('custom_data') or {}
                    if not custom:
                        custom = order.get('meta', {}).get('custom_data') or {}
                    if str(custom.get('discord_user_id', '')) == uid_str:
                        await self._fulfill(row)
                        await _complete_checkout(row['checkout_id'])
                        found = True
                        break

            if found:
                await ctx.send(embed=discord.Embed(
                    title='Payment verified!',
                    description=f'Your **{row["tier"]}** subscription is now active.',
                    color=config.COLORS['success'],
                ), ephemeral=True)
            else:
                await ctx.send(embed=discord.Embed(
                    description='Payment not completed yet. Finish the checkout and try again in a moment.',
                    color=config.COLORS['warning'],
                ), ephemeral=True)

        except Exception as e:
            logger.error(f'verifypayment error: {e}', exc_info=True)
            await ctx.send(embed=discord.Embed(
                description='Could not verify payment. Try again later.',
                color=config.COLORS['error'],
            ), ephemeral=True)


async def setup(bot: commands.Bot):
    await init_ls_table()
    await bot.add_cog(LemonSqueezyPayment(bot))
