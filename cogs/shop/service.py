"""
cogs/shop/service.py — shop business logic.

Phase 3b.2: extracted verbatim from cogs/shop/__init__.py. Functions here
implement purchase flows, item application (daily/work reset, streak restore),
and mystery box opening. Embed-builder helper _shop_embed renders the
3-section shop view.

When the Shop cog's commands move into commands.py, they import from here.
"""
import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import random

import config
import database as db
from fish_data import RODS as _FISH_RODS

from .constants import (
    CURRENCY_EMOJI,
    PRESTIGE_ROLE_NAME,
    CONSUMABLE_KEYS,
    SHOP,
    SECTION_EMOJIS,
    _MYSTERY_PRIZES,
)


__all__ = [
    "_grant_prestige_role",
    "_items_by_currency",
    "_dur_str",
    "_shop_embed",
    "_apply_daily_reset",
    "_apply_work_reset",
    "_apply_streak_restore",
    "_open_mystery_box",
]


# ─── Helper bodies (verbatim from source) ───────────────────────────────────

async def _grant_prestige_role(ctx: commands.Context) -> bool:
    if not ctx.guild or not ctx.guild.me.guild_permissions.manage_roles:
        return False

    role = discord.utils.get(ctx.guild.roles, name=PRESTIGE_ROLE_NAME)
    if role is None:
        try:
            role = await ctx.guild.create_role(
                name=PRESTIGE_ROLE_NAME,
                color=discord.Color(0xf1c40f),
                mentionable=False,
                reason='Tainment+ prestige badge role',
            )
        except discord.HTTPException:
            return False

    if role in ctx.author.roles:
        return True

    if role >= ctx.guild.me.top_role:
        return False

    try:
        await ctx.author.add_roles(role, reason='Purchased Prestige Badge')
        return True
    except discord.HTTPException:
        return False


def _items_by_currency(currency: str) -> dict[str, dict]:
    return {k: v for k, v in SHOP.items() if v['currency'] == currency}


def _dur_str(seconds: int | None) -> str:
    if seconds is None:
        return 'Permanent'
    if seconds >= 3600:
        return f"{seconds // 3600}h"
    return f"{seconds // 60}m"


def _shop_embed(currency: str) -> discord.Embed:
    items = _items_by_currency(currency)
    emoji = SECTION_EMOJIS[currency]
    embed = discord.Embed(
        title=f"{emoji} {currency.capitalize()} Shop",
        description=f"Use `t!buy <item_id>` to purchase.\nCheck your {currency} with `t!balance`.",
        color=config.COLORS['gold'] if currency == 'coins' else config.COLORS['purple'] if currency == 'gems' else config.COLORS['info'],
    )
    for key, item in items.items():
        dur = "Single Use" if key in CONSUMABLE_KEYS else _dur_str(item['duration'])
        # Rod items: append fishing level requirement
        rod_key = key[4:] if key.startswith('rod_') else None
        lvl_note = ""
        if rod_key and rod_key in _FISH_RODS:
            min_lvl = _FISH_RODS[rod_key].get('min_level', 1)
            if min_lvl > 1:
                lvl_note = f" | **Req. Fishing Lvl {min_lvl}**"
        embed.add_field(
            name=f"{item['emoji']} {item['name']}  —  {item['price']:,} {emoji}",
            value=f"{item['description']}{lvl_note}  *({dur})*\n**Buy:** `t!buy {key}`",
            inline=False,
        )
    embed.set_footer(text="Active items are shown in t!inventory and t!profile")
    return embed


async def _apply_daily_reset(user_id: int):
    await db.update_economy_field(user_id, last_daily=None, daily_streak=0)


async def _apply_work_reset(user_id: int):
    await db.update_economy_field(user_id, last_work=None)


async def _apply_streak_restore(user_id: int) -> int:
    """Restore previous streak. Returns the restored value (0 if nothing to restore)."""
    eco = await db.get_economy(user_id)
    if not eco:
        return 0
    prev = eco['previous_daily_streak'] if 'previous_daily_streak' in eco.keys() else 0
    if prev and prev > 0:
        await db.update_economy_field(user_id, daily_streak=prev, previous_daily_streak=0)
        return prev
    return 0


async def _open_mystery_box(user_id: int) -> tuple[str, str]:
    """Roll a mystery box prize, grant it, return (label, emoji)."""
    import random
    weights = [p[4] for p in _MYSTERY_PRIZES]
    prize = random.choices(_MYSTERY_PRIZES, weights=weights, k=1)[0]
    kind, value, label, emoji, _ = prize

    if kind == 'coins':
        await db.earn_currency(user_id, 'coins', value)
    elif kind == 'gems':
        await db.earn_currency(user_id, 'gems', value)
    elif kind == 'tokens':
        await db.earn_currency(user_id, 'tokens', value)
    elif kind == 'item':
        await db.add_inventory_item(user_id, value, allow_stack=True)

    return label, emoji
