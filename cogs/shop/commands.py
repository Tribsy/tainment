"""
cogs/shop/commands.py — Shop cog (slash + prefix commands).

Phase 3b.2: extracted verbatim from cogs/shop/__init__.py. The Shop class
holds command bodies. Business logic is in service.py; UI Views in views.py;
constants in constants.py.
"""
import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import random
import logging

import config
from config import SHOP_ITEMS
import database as db
from fish_data import RODS

from .constants import (
    CURRENCY_EMOJI,
    PRESTIGE_ROLE_NAME,
    CONSUMABLE_KEYS,
    SHOP,
    SECTION_EMOJIS,
)
from .service import *  # noqa: F401, F403  (re-exports the 8 helpers)
from .views import ShopCurrencySelect, ShopView

logger = logging.getLogger("tainment.shop.commands")


# ─── Shop cog ───────────────────────────────────────────────────────────────

class Shop(commands.Cog, name="Shop"):
    """Multi-currency item shop."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='shop', description='Browse the item shop (coins / gems / tokens)')
    async def shop_cmd(self, ctx: commands.Context, section: str = None):
        if section and section.lower() in ('coins', 'gems', 'tokens'):
            embed = _shop_embed(section.lower())
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Tainment+ Shop",
                description=(
                    "Three currencies, three shops!\n\n"
                    f"\U0001fa99 **Coins** — earn from daily, work, gambling\n"
                    f"\U0001f48e **Gems** — earn by winning games & skill challenges\n"
                    f"\U0001f3ab **Tokens** — earn from duels, snap, scramble, streaks\n\n"
                    "Use the dropdown or `t!shop coins/gems/tokens`"
                ),
                color=config.COLORS['primary'],
            )
            view = ShopView()
            await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name='buy', description='Buy an item from the shop')
    async def buy(self, ctx: commands.Context, *, item: str):
        item_key = item.lower().strip().replace(' ', '_')
        if item_key not in SHOP:
            # Try fuzzy: find keys that contain the search term
            matches = [k for k in SHOP if item.lower() in k or item.lower() in SHOP[k]['name'].lower()]
            if len(matches) == 1:
                item_key = matches[0]
            else:
                keys = ', '.join(f'`{k}`' for k in SHOP)
                await ctx.send(embed=discord.Embed(
                    description=f"Item not found. Available: {keys}",
                    color=config.COLORS['error'],
                ))
                return

        await db.ensure_user(ctx.author.id, ctx.author.name)
        item_data = SHOP[item_key]
        currency = item_data['currency']
        price = item_data['price']

        bal = await db.get_currency(ctx.author.id, currency)
        if bal < price:
            emoji = CURRENCY_EMOJI[currency]
            await ctx.send(embed=discord.Embed(
                description=f"You need `{price:,}` {emoji} but only have `{bal:,}` {emoji}.",
                color=config.COLORS['error'],
            ))
            return

        # Permanent items — check already owned
        _consumables = CONSUMABLE_KEYS
        if item_data['duration'] is None and item_key not in _consumables:
            if await db.has_active_item(ctx.author.id, item_key):
                await ctx.send(embed=discord.Embed(
                    description="You already own this item.",
                    color=config.COLORS['warning'],
                ))
                return

        expires_at = None
        if item_data['duration']:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=item_data['duration'])).isoformat()

        await db.spend_currency(ctx.author.id, currency, price)

        # Mystery box: open immediately, never stored in inventory
        if item_key == 'mystery_box':
            prize_label, prize_emoji = await _open_mystery_box(ctx.author.id)
            await ctx.send(embed=discord.Embed(
                title="📦 Mystery Box Opened!",
                description=(
                    f"You spent **1,200** 🪙 and cracked open a Mystery Box...\n\n"
                    f"{prize_emoji} You got: **{prize_label}**!"
                ),
                color=config.COLORS['gold'],
            ))
            return

        await db.add_inventory_item(ctx.author.id, item_key, expires_at, allow_stack=item_key in _consumables)
        prestige_role_granted = False
        if item_key == 'prestige_badge':
            prestige_role_granted = await _grant_prestige_role(ctx)

        emoji = CURRENCY_EMOJI[currency]
        extra_note = "\nRole granted: **✨ Prestige**" if prestige_role_granted else ""
        embed = discord.Embed(
            title="Purchase successful!",
            description=(
                f"Bought **{item_data['name']}** for `{price:,}` {emoji}\n"
                f"{item_data['description']}{extra_note}"
            ),
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.command(name='use', description='Use a consumable item from your inventory')
    async def use_item(self, ctx: commands.Context, item_key: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        item_key = item_key.lower()

        _use_handlers = {
            'daily_reset':    _apply_daily_reset,
            'work_reset':     _apply_work_reset,
            'streak_restore': _apply_streak_restore,
        }
        if item_key not in _use_handlers:
            await ctx.send(embed=discord.Embed(
                description=f"`{item_key}` is not a usable consumable.",
                color=config.COLORS['error'],
            ))
            return

        removed = await db.remove_inventory_item(ctx.author.id, item_key)
        if not removed:
            item_name = SHOP_ITEMS.get(item_key, {}).get('name', item_key)
            await ctx.send(embed=discord.Embed(
                description=f"You don't have a **{item_name}** in your inventory. Buy one with `t!buy {item_key}`.",
                color=config.COLORS['error'],
            ))
            return

        item_name = SHOP_ITEMS[item_key]['name']
        if item_key == 'streak_restore':
            prev = await _apply_streak_restore(ctx.author.id)
            desc = (
                f"Your daily streak has been restored to **{prev} days**! Item removed from inventory."
                if prev else
                "No saved streak to restore (streak hadn't reset recently). Item removed from inventory."
            )
        else:
            await _use_handlers[item_key](ctx.author.id)
            desc = f"Used **{item_name}** — cooldown reset. Item removed from inventory."

        await ctx.send(embed=discord.Embed(
            title="Item Used!",
            description=desc,
            color=config.COLORS['success'],
        ))

    @commands.hybrid_command(name='balance', aliases=['bal'], description='Check your currency balances')
    async def balance(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        await db.ensure_user(target.id, target.name)
        eco = await db.get_economy(target.id)

        coins = eco['coins'] if eco else 0
        gems = eco['gems'] if eco else 0
        tokens = eco['tokens'] if eco else 0
        total_earned = eco['total_earned'] if eco else 0

        embed = discord.Embed(
            title=f"{target.display_name}'s Wallet",
            color=config.COLORS['gold'],
        )
        embed.add_field(name="\U0001fa99 Coins", value=f"`{coins:,}`", inline=True)
        embed.add_field(name="\U0001f48e Gems", value=f"`{gems:,}`", inline=True)
        embed.add_field(name="\U0001f3ab Tokens", value=f"`{tokens:,}`", inline=True)
        embed.add_field(name="Total Coins Earned", value=f"`{total_earned:,}`", inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Earn gems by winning games | Tokens from duels & events")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='inventory', aliases=['inv'], description='View your active items')
    async def inventory(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        await db.ensure_user(target.id, target.name)
        items = await db.get_inventory(target.id)

        now = datetime.now(timezone.utc)
        item_groups = {}  # key -> {name, desc, count, time_str (oldest expiry)}

        for row in items:
            key = row['item_key']
            item_data = SHOP.get(key)
            if not item_data:
                continue

            # Check if expired
            if row['expires_at']:
                exp = datetime.fromisoformat(row['expires_at']).replace(tzinfo=timezone.utc)
                if exp < now:
                    continue
                remaining = int((exp - now).total_seconds())
                h, s = divmod(remaining, 3600)
                m = s // 60
                time_str = f"Expires in {h}h {m}m"
            else:
                time_str = "Permanent"

            # Group by key
            if key not in item_groups:
                item_groups[key] = {
                    'name': item_data['name'],
                    'desc': item_data['description'],
                    'count': 0,
                    'time_str': time_str,
                }
            item_groups[key]['count'] += 1
            # Update to earliest expiry time if this one expires sooner
            if time_str != "Permanent" and item_groups[key]['time_str'] == "Permanent":
                item_groups[key]['time_str'] = time_str
            elif time_str != "Permanent" and item_groups[key]['time_str'] != "Permanent":
                # Keep the one that expires sooner (shows first)
                pass

        if not item_groups:
            await ctx.send(embed=discord.Embed(
                description=f"{target.display_name} has no active items. Visit `t!shop`!",
                color=config.COLORS['warning'],
            ))
            return

        embed = discord.Embed(title=f"{target.display_name}'s Inventory", color=config.COLORS['primary'])
        for key, group in item_groups.items():
            count_prefix = f"{group['count']}x " if group['count'] > 1 else ""
            name = f"{count_prefix}{group['name']}"
            value = f"{group['desc']}\n*{group['time_str']}*"
            embed.add_field(name=name, value=value, inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='transfer', aliases=['give', 'pay'], description='Transfer coins to another user')
    async def transfer(self, ctx: commands.Context, target: discord.Member, amount: int, currency: str = 'coins'):
        currency = currency.lower()
        if currency not in CURRENCY_EMOJI:
            await ctx.send(embed=discord.Embed(
                description="Currency must be `coins`, `gems`, or `tokens`.",
                color=config.COLORS['error'],
            ))
            return
        if target.id == ctx.author.id or target.bot:
            await ctx.send(embed=discord.Embed(description="Invalid target.", color=config.COLORS['error']))
            return
        if amount <= 0:
            await ctx.send(embed=discord.Embed(description="Amount must be positive.", color=config.COLORS['error']))
            return

        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_user(target.id, target.name)
        bal = await db.get_currency(ctx.author.id, currency)

        if amount > bal:
            emoji = CURRENCY_EMOJI[currency]
            await ctx.send(embed=discord.Embed(
                description=f"You only have `{bal:,}` {emoji}.",
                color=config.COLORS['error'],
            ))
            return

        await db.spend_currency(ctx.author.id, currency, amount)
        await db.earn_currency(target.id, currency, amount)

        emoji = CURRENCY_EMOJI[currency]
        embed = discord.Embed(
            title="Transfer complete!",
            description=f"Sent **{amount:,}** {emoji} to {target.mention}.",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.command(name='removeitem', description='[OWNER] Remove an item from a user\'s inventory')
    @commands.is_owner()
    async def removeitem(self, ctx: commands.Context, user: discord.Member, *, item_key: str):
        """Remove a single instance of an item from a user's inventory. Owner-only."""
        item_key = item_key.strip().lower()
        
        # Validate item exists in shop
        if item_key not in SHOP:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Item `{item_key}` not found in shop.",
                color=config.COLORS['error'],
            ))
            return
        
        await db.ensure_user(user.id, user.name)
        
        # Try to remove the item
        success = await db.remove_inventory_item(user.id, item_key)
        
        if success:
            item_name = SHOP[item_key]['name']
            await ctx.send(embed=discord.Embed(
                description=f"✅ Removed **{item_name}** from {user.mention}'s inventory.",
                color=config.COLORS['success'],
            ))
        else:
            item_name = SHOP[item_key]['name']
            await ctx.send(embed=discord.Embed(
                description=f"❌ {user.mention} doesn't have **{item_name}** in their inventory.",
                color=config.COLORS['error'],
            ))


# ─── Setup ──────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
