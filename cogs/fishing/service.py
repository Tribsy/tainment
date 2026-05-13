"""
cogs/fishing/service.py — fishing business logic.

Phase 3d: extracted verbatim from cogs/fishing/__init__.py. Functions here
build the weighted catch pool, pick a fish, look up the player's equipped
rod, and compute fishing-level XP math.
"""
import discord
from discord.ext import commands
import random
import aiosqlite
from datetime import datetime, timezone, timedelta

import config
import database as db

from .data import FISH, TIERS, RODS, get_rod_info, get_catchable_tiers, get_tier_for_fish
from .constants import TIER_EMOJIS, TIER_COLORS, TIER_XP, TIER_GEMS, TIER_TOKENS


__all__ = [
    "_build_weighted_pool",
    "_pick_fish",
    "_get_rod_tier_from_inventory",
    "_get_rod_name_from_tier",
    "_get_rod_key_from_tier",
    "_cooldown_for_rod",
    "_fishing_level_from_xp",
    "_xp_in_current_level",
    "_check_premium_bait",
]


# ─── Function bodies (verbatim from source) ─────────────────────────────────

def _build_weighted_pool(rod_tier: int, bait_active: bool, subscription_tier: str) -> list[tuple]:
    """
    Returns list of (tier_key, fish_name, min_coins, max_coins, base_weight) tuples.
    Only includes fish catchable with the given rod_tier.
    """
    pool = []
    for tier_key, tier_info in TIERS.items():
        if tier_info['min_rod'] > rod_tier:
            continue  # rod too weak for this tier
        fish_list = FISH.get(tier_key, [])
        base_w = tier_info.get('base_weight', tier_info.get('weight', 1.0))

        # Subscription bonuses
        if subscription_tier == 'Premium':
            if tier_key in ('rare', 'epic'):
                base_w = int(base_w * 1.15)
        elif subscription_tier == 'Pro':
            if tier_key in ('rare', 'epic', 'legendary'):
                base_w = int(base_w * 1.30)

        # Premium Bait boosts rare+ tiers
        if bait_active:
            if tier_key in ('rare', 'epic', 'legendary', 'mythic', 'ancient', 'celestial', 'void'):
                base_w = int(base_w * 1.40)

        # Rod tier bonus: higher rods boost rarer tiers
        rod_bonus_tiers = ['uncommon', 'rare', 'epic', 'legendary', 'mythic', 'ancient', 'celestial', 'void']
        if tier_key in rod_bonus_tiers:
            idx = rod_bonus_tiers.index(tier_key)
            rod_bonus = 1.0 + (rod_tier * 0.12 * max(0, idx - 1))
            base_w = int(base_w * rod_bonus)

        for fish_tuple in fish_list:
            name, min_c, max_c, fish_min_rod = fish_tuple
            if fish_min_rod > rod_tier:
                continue
            pool.append((tier_key, name, min_c, max_c, base_w))

    return pool


def _pick_fish(rod_tier: int, fishing_level: int, bait_active: bool, sub_tier: str):
    """Pick a random fish. Returns (tier_key, name, min_coins, max_coins)."""
    pool = _build_weighted_pool(rod_tier, bait_active, sub_tier)
    if not pool:
        # Fallback: basic trash
        return ('trash', 'Rusty Can', 0, 0)

    # Fishing level bonus: every 5 levels, slightly boost rare+ weights
    adjusted_pool = []
    level_mult = 1.0 + min(fishing_level // 5, 8) * 0.05
    level_boost_tiers = {'rare', 'epic', 'legendary', 'mythic', 'ancient', 'celestial', 'void'}
    for entry in pool:
        tier_key, name, min_c, max_c, w = entry
        if tier_key in level_boost_tiers:
            w = int(w * level_mult)
        adjusted_pool.append((tier_key, name, min_c, max_c, w))

    weights = [e[4] for e in adjusted_pool]
    chosen = random.choices(adjusted_pool, weights=weights, k=1)[0]
    return (chosen[0], chosen[1], chosen[2], chosen[3])


def _get_rod_tier_from_inventory(inventory_rows, equipped_rod: str | None = None, fishing_level: int = 0) -> int:
    """Return the highest usable rod tier the player owns and meets the level requirement for."""
    raw_keys = {row['item_key'] for row in inventory_rows}
    # Normalize: shop stores rods as rod_<key>, RODS dict uses bare keys
    rod_keys = {k[4:] if k.startswith('rod_') else k for k in raw_keys}

    def _meets_level(rod_key: str) -> bool:
        return fishing_level >= RODS[rod_key].get('min_level', 1)

    # If player has manually equipped a rod, still owns it, and meets the level req, use it
    if equipped_rod and equipped_rod in RODS:
        is_owned = equipped_rod in rod_keys or RODS[equipped_rod]['tier'] == 0
        if is_owned and _meets_level(equipped_rod):
            return RODS[equipped_rod]['tier']

    # Auto-select highest owned rod the player has the level for
    best = 0
    for rod_key, rod_info in RODS.items():
        if rod_key in rod_keys and _meets_level(rod_key) and rod_info['tier'] > best:
            best = rod_info['tier']
    return best


def _get_rod_name_from_tier(tier: int) -> str:
    for rod_key, rod_info in RODS.items():
        if rod_info['tier'] == tier:
            return rod_info['name']
    return "No Rod"


def _get_rod_key_from_tier(tier: int) -> str | None:
    for rod_key, rod_info in RODS.items():
        if rod_info['tier'] == tier:
            return rod_key
    return None


def _cooldown_for_rod(rod_tier: int) -> int:
    """Cooldown in seconds based on rod tier."""
    rod_key = _get_rod_key_from_tier(rod_tier)
    if rod_key and rod_key in RODS:
        return RODS[rod_key]['cooldown']
    return 20


def _fishing_level_from_xp(total_xp: int) -> int:
    level, remaining = 0, total_xp
    needed = 100
    while remaining >= needed:
        remaining -= needed
        level += 1
        needed = int(needed * 1.4)
    return level


def _xp_in_current_level(total_xp: int) -> tuple[int, int]:
    remaining = total_xp
    needed = 100
    while True:
        if remaining < needed:
            return remaining, needed
        remaining -= needed
        needed = int(needed * 1.4)


async def _check_premium_bait(user_id: int) -> bool:
    """Check if the user has active premium bait (time-based, ~1 hour)."""
    async with aiosqlite.connect(config.DB_PATH) as db_conn:
        async with db_conn.execute("""
            SELECT expires_at FROM inventory
            WHERE user_id = ? AND item_key = 'premium_bait'
            AND expires_at > datetime('now')
            ORDER BY expires_at DESC LIMIT 1
        """, (user_id,)) as cur:
            row = await cur.fetchone()
            return row is not None
