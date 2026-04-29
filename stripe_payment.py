"""
Real Stripe payment integration for Tainment+ subscriptions.

Flow:
1. User runs t!upgrade <tier>
2. Bot creates a Stripe Checkout Session (one-time payment)
3. Bot sends the checkout URL to the user (ephemeral)
4. User completes payment on Stripe's hosted page
5. Background task polls Stripe every 2 minutes to detect completed sessions
6. Bot upgrades the user's subscription automatically

Setup:
- pip install stripe
- Add STRIPE_SECRET_KEY to .env
- Optionally set STRIPE_WEBHOOK_SECRET for webhook support (see below)
"""

import discord
from discord.ext import commands, tasks
import stripe
import os
import logging
import aiosqlite
from datetime import datetime, timezone, timedelta
import asyncio
import config
import database as db
from reply_utils import send_reply

logger = logging.getLogger('tainment.stripe')

DISCOUNTS = {1: 0, 3: 0.10, 6: 0.15, 12: 0.20}
TIER_ORDER = {'Basic': 0, 'Premium': 1, 'Pro': 2}


def get_stripe_key() -> str | None:
    return os.getenv('STRIPE_SECRET_KEY', '')


def calculate_price(tier: str, months: int) -> float:
    base = config.SUBSCRIPTION_TIERS[tier]['price']
    discount = DISCOUNTS.get(months, 0)
    return round(base * months * (1 - discount), 2)


async def init_stripe_table():
    async with aiosqlite.connect(config.DB_PATH) as db_conn:
        await db_conn.execute("""
            CREATE TABLE IF NOT EXISTS stripe_sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER,
                tier TEXT,
                months INTEGER,
                amount REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        await db_conn.commit()


async def store_session(session_id: str, user_id: int, tier: str, months: int, amount: float):
    async with aiosqlite.connect(config.DB_PATH) as db_conn:
        await db_conn.execute(
            "INSERT OR IGNORE INTO stripe_sessions (session_id, user_id, tier, months, amount) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, tier, months, amount)
        )
        await db_conn.commit()


async def get_pending_sessions():
    async with aiosqlite.connect(config.DB_PATH) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT * FROM stripe_sessions WHERE status = 'pending'"
        ) as cur:
            return await cur.fetchall()


async def complete_stripe_session(session_id: str):
    async with aiosqlite.connect(config.DB_PATH) as db_conn:
        await db_conn.execute(
            "UPDATE stripe_sessions SET status = 'completed', completed_at = datetime('now') WHERE session_id = ?",
            (session_id,)
        )
        await db_conn.commit()


async def expire_stripe_session(session_id: str):
    async with aiosqlite.connect(config.DB_PATH) as db_conn:
        await db_conn.execute(
            "UPDATE stripe_sessions SET status = 'expired' WHERE session_id = ?",
            (session_id,)
        )
        await db_conn.commit()


class StripePayment(commands.Cog, name="StripePayment"):
    """Real Stripe payment processing for subscriptions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stripe_key = get_stripe_key()
        if self.stripe_key:
            stripe.api_key = self.stripe_key
            self.poll_sessions.start()
            logger.info("Stripe integration enabled.")
        else:
            logger.warning("STRIPE_SECRET_KEY not set. Stripe payments disabled.")

    def cog_unload(self):
        if self.stripe_key:
            self.poll_sessions.cancel()

    def is_configured(self) -> bool:
        return bool(self.stripe_key)

    @tasks.loop(minutes=2)
    async def poll_sessions(self):
        """Check pending Stripe sessions and fulfill completed ones."""
        sessions = await get_pending_sessions()
        for session in sessions:
            try:
                cs = stripe.checkout.Session.retrieve(session['session_id'])
                created_ago = (datetime.now(timezone.utc) - datetime.fromtimestamp(cs.created, tz=timezone.utc)).total_seconds()

                if cs.payment_status == 'paid':
                    await self._fulfill_subscription(
                        user_id=session['user_id'],
                        tier=session['tier'],
                        months=session['months'],
                        amount=session['amount'],
                        session_id=session['session_id'],
                    )
                    await complete_stripe_session(session['session_id'])
                elif created_ago > 3600:
                    # Session expired (Stripe sessions last 24h but we cut off at 1h)
                    async with aiosqlite.connect(config.DB_PATH) as db_conn:
                        await db_conn.execute(
                            "UPDATE stripe_sessions SET status = 'expired' WHERE session_id = ?",
                            (session['session_id'],)
                        )
                        await db_conn.commit()
            except stripe.StripeError as e:
                logger.error(f"Stripe error polling session {session['session_id']}: {e}")
            except Exception as e:
                logger.error(f"Error processing session {session['session_id']}: {e}", exc_info=True)

    @poll_sessions.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

    async def _fulfill_subscription(self, user_id: int, tier: str, months: int, amount: float, session_id: str):
        old_tier = await db.get_tier(user_id)
        now = datetime.now(timezone.utc)
        sub = await db.get_subscription(user_id)

        if sub and sub['end_date']:
            existing_end = datetime.fromisoformat(sub['end_date']).replace(tzinfo=timezone.utc)
            start = max(existing_end, now)
        else:
            start = now

        end_date = start + timedelta(days=months * 30)
        grace_end = end_date + timedelta(days=3)

        await db.update_subscription(user_id, tier, end_date.isoformat(), grace_end.isoformat())
        await db.log_subscription_change(user_id, old_tier, tier, reason=f"Stripe payment {session_id}")
        await db.record_payment(user_id, session_id, amount, tier, months, 'completed')

        ts = int(end_date.timestamp())
        try:
            user = await self.bot.fetch_user(user_id)
            embed = discord.Embed(
                title="Payment Confirmed!",
                description=(
                    f"Your **{tier}** subscription is now active!\n\n"
                    f"Duration: `{months}` month{'s' if months != 1 else ''}\n"
                    f"Active until: <t:{ts}:F>\n"
                    f"Amount paid: `${amount:.2f}`"
                ),
                color=config.COLORS['success'],
            )
            embed.set_footer(text="Thank you for supporting Tainment+!")
            await user.send(embed=embed)
        except Exception:
            pass
        logger.info(f"Fulfilled {tier} x{months}mo for user {user_id} via session {session_id}")

    async def create_checkout(self, ctx: commands.Context, tier: str, months: int) -> bool:
        """Create a Stripe checkout session and send the link to the user. Returns True on success."""
        if not self.is_configured():
            return False

        amount = calculate_price(tier, months)
        amount_cents = int(amount * 100)
        discount_pct = DISCOUNTS.get(months, 0)

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='payment',
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': amount_cents,
                        'product_data': {
                            'name': f'Tainment+ {tier} — {months} month{"s" if months != 1 else ""}',
                            'description': (
                                f'Discord bot subscription. '
                                f'{"Save " + str(int(discount_pct*100)) + "%!" if discount_pct else ""}'
                            ),
                        },
                    },
                    'quantity': 1,
                }],
                metadata={
                    'discord_user_id': str(ctx.author.id),
                    'tier': tier,
                    'months': str(months),
                },
                success_url='https://discord.com/channels/@me',
                cancel_url='https://discord.com/channels/@me',
                expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            )

            await store_session(session.id, ctx.author.id, tier, months, amount)

            embed = discord.Embed(
                title=f"Tainment+ {tier} Checkout",
                description=(
                    f"Click below to complete your payment securely via Stripe.\n\n"
                    f"**{tier}** — {months} month{'s' if months != 1 else ''}\n"
                    f"Total: **${amount:.2f}** USD"
                    + (f" *(Save {int(discount_pct*100)}%!)*" if discount_pct else "") +
                    f"\n\nYour subscription will be activated **automatically** after payment.\n"
                    f"Link expires in **1 hour**."
                ),
                color=config.COLORS['primary'],
            )
            embed.set_footer(text="Powered by Stripe | Secure payment")

            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Pay with Stripe",
                url=session.url,
                style=discord.ButtonStyle.link,
                emoji='\U0001f4b3',
            ))

            try:
                await ctx.author.send(embed=embed, view=view)
                await send_reply(
                    ctx,
                    embed=discord.Embed(
                        description="Checkout link sent to your DMs!",
                        color=config.COLORS['success'],
                    ),
                    ephemeral=True,
                )
            except discord.Forbidden:
                # DMs closed — send ephemerally in channel
                await send_reply(ctx, embed=embed, view=view, ephemeral=True)

            return True

        except stripe.StripeError as e:
            logger.error(f"Stripe checkout creation failed: {e}")
            await send_reply(ctx, embed=discord.Embed(
                description=f"Payment system error. Please try again later.\n`{e.user_message}`",
                color=config.COLORS['error'],
            ), ephemeral=True)
            return False

    @commands.hybrid_command(name='verifypayment', aliases=['verifypay', 'checkpay'], description='Manually check if your payment was processed')
    async def verifypayment(self, ctx: commands.Context):
        """Check if any of your pending Stripe sessions completed."""
        if not self.is_configured():
            await send_reply(ctx, embed=discord.Embed(description="Stripe not configured.", color=config.COLORS['error']), ephemeral=True)
            return

        async with aiosqlite.connect(config.DB_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute(
                "SELECT * FROM stripe_sessions WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
                (ctx.author.id,)
            ) as cur:
                session = await cur.fetchone()

        if not session:
            await send_reply(ctx, embed=discord.Embed(description="No pending payment found.", color=config.COLORS['warning']), ephemeral=True)
            return

        await send_reply(ctx, embed=discord.Embed(description="Checking your payment...", color=config.COLORS['info']), ephemeral=True)

        try:
            cs = stripe.checkout.Session.retrieve(session['session_id'])
            if cs.payment_status == 'paid':
                await self._fulfill_subscription(
                    ctx.author.id, session['tier'], session['months'], session['amount'], session['session_id']
                )
                await complete_stripe_session(session['session_id'])
                await send_reply(ctx, embed=discord.Embed(
                    title="Payment verified!",
                    description=f"Your **{session['tier']}** subscription is now active.",
                    color=config.COLORS['success'],
                ), ephemeral=True)
            else:
                await send_reply(ctx, embed=discord.Embed(
                    description="Payment not completed yet. Finish the checkout and try again.",
                    color=config.COLORS['warning'],
                ), ephemeral=True)
        except stripe.StripeError as e:
            await send_reply(ctx, embed=discord.Embed(description=f"Could not verify: `{e.user_message}`", color=config.COLORS['error']), ephemeral=True)


async def setup(bot: commands.Bot):
    await init_stripe_table()
    await bot.add_cog(StripePayment(bot))
