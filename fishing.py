"""
Fishing game — 2300+ fish across 10 tiers, 11 rod types, bait system.
Commands: fish, fishbag, sell, fishstats, fishtop, rods, bait
"""

import discord
from discord.ext import commands
import random
import aiosqlite
from datetime import datetime, timezone, timedelta
import config
import database as db
from fish_data import (
    FISH, TIERS, RODS,
    get_rod_info, get_catchable_tiers, get_tier_for_fish,
)

# Flatten all fish into a lookup: (tier_key, name_lower) -> (name, min_coins, max_coins, min_rod)
# Build an indexed list per tier for weighted selection.

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
        base_w = tier_info['base_weight']

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


def _get_rod_tier_from_inventory(inventory_rows) -> int:
    """Return the highest rod tier the user owns."""
    rod_keys = {row['item_key'] for row in inventory_rows}
    best = 0
    for rod_key, rod_info in RODS.items():
        if rod_key in rod_keys and rod_info['tier'] > best:
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


# Tier display helpers
TIER_EMOJIS = {
    'trash': '🗑️', 'common': '🐟', 'uncommon': '🐠', 'rare': '🐡',
    'epic': '✨', 'legendary': '🌟', 'mythic': '💫', 'ancient': '🏺',
    'celestial': '🌠', 'void': '⬛',
}
TIER_COLORS = {
    'trash': 0x7f8c8d, 'common': 0x95a5a6, 'uncommon': 0x2ecc71,
    'rare': 0x3498db, 'epic': 0xe040fb, 'legendary': 0xf39c12,
    'mythic': 0x9b59b6, 'ancient': 0x8e44ad, 'celestial': 0x00e5ff,
    'void': 0x1a1a2e,
}

# XP per tier
TIER_XP = {
    'trash': 2, 'common': 10, 'uncommon': 25, 'rare': 60,
    'epic': 120, 'legendary': 250, 'mythic': 400, 'ancient': 600,
    'celestial': 900, 'void': 1500,
}

# Gem rewards per tier
TIER_GEMS = {
    'trash': 0, 'common': 0, 'uncommon': 0, 'rare': 1,
    'epic': 2, 'legendary': 5, 'mythic': 10, 'ancient': 20,
    'celestial': 50, 'void': 100,
}

# Token rewards per tier
TIER_TOKENS = {
    'trash': 0, 'common': 0, 'uncommon': 0, 'rare': 0,
    'epic': 1, 'legendary': 2, 'mythic': 4, 'ancient': 8,
    'celestial': 15, 'void': 30,
}


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


class Fishing(commands.Cog, name="Fishing"):
    """Fishing game with 2300+ fish, 11 rod types, and a bait system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='fish', description='Cast your line and catch a fish!')
    async def fish(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_fishing_row(ctx.author.id)

        stats = await db.get_fishing_stats(ctx.author.id)
        inv = await db.get_inventory(ctx.author.id)
        rod_tier = _get_rod_tier_from_inventory(inv)
        cooldown = _cooldown_for_rod(rod_tier)

        # Check cooldown
        if stats['last_fished']:
            last_dt = datetime.fromisoformat(stats['last_fished']).replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if elapsed < cooldown:
                remaining = cooldown - elapsed
                await ctx.send(embed=discord.Embed(
                    title="Line not ready!",
                    description=f"Wait **{remaining:.0f}s** before casting again.",
                    color=config.COLORS['warning'],
                ))
                return

        fishing_level = _fishing_level_from_xp(stats['fishing_xp'])
        bait_active = await _check_premium_bait(ctx.author.id)
        sub_tier = await db.get_tier(ctx.author.id)

        tier_key, fish_name, min_coins, max_coins = _pick_fish(rod_tier, fishing_level, bait_active, sub_tier)
        coins = random.randint(min_coins, max_coins) if max_coins > 0 else 0
        xp_gain = TIER_XP.get(tier_key, 10)
        gems = TIER_GEMS.get(tier_key, 0)
        tokens = TIER_TOKENS.get(tier_key, 0)

        # Apply Pro subscription fishing bonuses
        if sub_tier == 'Pro':
            xp_gain = xp_gain * 2

        new_xp = stats['fishing_xp'] + xp_gain
        new_level = _fishing_level_from_xp(new_xp)
        leveled_up = new_level > fishing_level

        biggest_coins = stats['biggest_catch_coins'] or 0
        new_biggest_type = stats['biggest_catch_type']
        fish_key = fish_name.lower().replace(' ', '_')
        if coins > biggest_coins:
            biggest_coins = coins
            new_biggest_type = fish_key

        await db.add_fish_to_bag(ctx.author.id, fish_key)
        await db.update_fishing_stats(
            ctx.author.id,
            total_caught=stats['total_caught'] + 1,
            fishing_xp=new_xp,
            fishing_level=new_level,
            last_fished=datetime.now(timezone.utc).isoformat(),
            biggest_catch_type=new_biggest_type,
            biggest_catch_coins=biggest_coins,
        )

        tier_info = TIERS.get(tier_key, {})
        tier_label = tier_info.get('label', tier_key.title())
        emoji = TIER_EMOJIS.get(tier_key, '🐟')
        color = TIER_COLORS.get(tier_key, config.COLORS['primary'])
        rod_name = _get_rod_name_from_tier(rod_tier)

        if tier_key == 'trash':
            title = f"Reeled in... {emoji} {fish_name}"
            desc = f"*This is just junk.* Discard with `t!sell all`."
        else:
            val_str = f"~**{coins:,}** 🪙" if coins > 0 else "No sell value"
            extras = ""
            if gems:
                extras += f" + **{gems}** 💎"
            if tokens:
                extras += f" + **{tokens}** 🎫"
            desc = (
                f"**Tier:** {tier_label} {emoji}\n"
                f"**Sell value:** {val_str}{extras}\n"
                f"**XP gained:** +{xp_gain}"
            )
            if bait_active:
                desc += "  *(Bait active!)*"
            if leveled_up:
                desc += f"\n\n🎉 **Fishing Level Up! → Level {new_level}!**"
            desc += f"\n\nSell: `t!sell {fish_key}` or `t!sell all`"
            title = f"Caught {emoji} {fish_name}!"

        xp_now, xp_need = _xp_in_current_level(new_xp)
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(
            text=(
                f"Rod: {rod_name} (Tier {rod_tier})  |  "
                f"Fishing Lvl {new_level}  |  "
                f"XP {xp_now}/{xp_need}  |  "
                f"Cooldown {cooldown}s"
            )
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='fishbag', aliases=['fb', 'bag'], description='View your fish bag')
    async def fishbag(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        await db.ensure_user(target.id, target.name)
        fish_inv = await db.get_fish_inventory(target.id)

        if not fish_inv:
            await ctx.send(embed=discord.Embed(
                description=f"{target.display_name} has no fish. Use `t!fish` to catch some!",
                color=config.COLORS['warning'],
            ))
            return

        # Group by tier
        tier_buckets: dict[str, list] = {}
        total_est = 0
        for row in fish_inv:
            fkey = row['fish_key']
            qty = row['quantity']
            # Look up fish
            fish_name = fkey.replace('_', ' ').title()
            tier_key = get_tier_for_fish(fish_name)
            if tier_key is None:
                tier_key = 'common'
            tier_label = TIERS.get(tier_key, {}).get('label', tier_key.title())
            emoji = TIER_EMOJIS.get(tier_key, '🐟')

            # Estimate sell value
            fish_list = FISH.get(tier_key, [])
            min_c, max_c = 0, 0
            for ft in fish_list:
                if ft[0].lower().replace(' ', '_') == fkey:
                    min_c, max_c = ft[1], ft[2]
                    break
            avg = (min_c + max_c) // 2
            est = avg * qty
            total_est += est

            if tier_key not in tier_buckets:
                tier_buckets[tier_key] = []
            tier_buckets[tier_key].append(f"{emoji} **{fish_name}** ×{qty}  ~`{est:,}` 🪙")

        lines = []
        tier_order = ['void', 'celestial', 'ancient', 'mythic', 'legendary', 'epic', 'rare', 'uncommon', 'common', 'trash']
        for t in tier_order:
            if t in tier_buckets:
                tier_label = TIERS.get(t, {}).get('label', t.title())
                lines.append(f"**— {tier_label} —**")
                lines.extend(tier_buckets[t][:10])
                if len(tier_buckets[t]) > 10:
                    lines.append(f"*...+{len(tier_buckets[t])-10} more {tier_label}*")

        # Paginate if too long
        desc = "\n".join(lines[:50])
        if len(lines) > 50:
            desc += f"\n*...and more. Use t!sell all to cash out.*"

        embed = discord.Embed(
            title=f"🎣 {target.display_name}'s Fish Bag",
            description=desc or "Empty bag.",
            color=config.COLORS['primary'],
        )
        embed.set_footer(text=f"Est. sell value: ~{total_est:,} coins  |  t!sell all to cash out")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='sell', description='Sell fish from your bag')
    async def sell(self, ctx: commands.Context, *, target_fish: str = 'all'):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_fishing_row(ctx.author.id)

        fish_inv = await db.get_fish_inventory(ctx.author.id)
        if not fish_inv:
            await ctx.send(embed=discord.Embed(
                description="Your fish bag is empty! Use `t!fish` first.",
                color=config.COLORS['warning'],
            ))
            return

        target_fish = target_fish.lower().replace(' ', '_')
        if target_fish == 'all':
            to_sell = {row['fish_key']: row['quantity'] for row in fish_inv}
        else:
            to_sell = {row['fish_key']: row['quantity'] for row in fish_inv if row['fish_key'] == target_fish}
            if not to_sell:
                names = ', '.join(f"`{r['fish_key']}`" for r in fish_inv[:10])
                await ctx.send(embed=discord.Embed(
                    description=f"You don't have `{target_fish}`. Bag: {names}",
                    color=config.COLORS['error'],
                ))
                return

        total_coins, total_gems, total_tokens = 0, 0, 0
        sell_lines = []

        for fkey, qty in to_sell.items():
            fish_name = fkey.replace('_', ' ').title()
            tier_key = get_tier_for_fish(fish_name)
            if tier_key is None:
                tier_key = 'trash'

            emoji = TIER_EMOJIS.get(tier_key, '🐟')
            await db.sell_fish_from_bag(ctx.author.id, fkey, qty)

            if tier_key == 'trash':
                sell_lines.append(f"{emoji} {fish_name} ×{qty} → junk (0 🪙)")
                continue

            fish_list = FISH.get(tier_key, [])
            min_c, max_c = 0, 0
            for ft in fish_list:
                if ft[0].lower().replace(' ', '_') == fkey:
                    min_c, max_c = ft[1], ft[2]
                    break

            coins = sum(random.randint(min_c, max_c) for _ in range(qty)) if max_c > 0 else 0
            gems = TIER_GEMS.get(tier_key, 0) * qty
            tokens = TIER_TOKENS.get(tier_key, 0) * qty
            total_coins += coins
            total_gems += gems
            total_tokens += tokens

            val = f"**{coins:,}** 🪙"
            if gems:
                val += f" + **{gems}** 💎"
            if tokens:
                val += f" + **{tokens}** 🎫"
            sell_lines.append(f"{emoji} {fish_name} ×{qty} → {val}")

        if total_coins > 0:
            await db.earn_currency(ctx.author.id, 'coins', total_coins)
        if total_gems > 0:
            await db.earn_currency(ctx.author.id, 'gems', total_gems)
        if total_tokens > 0:
            await db.earn_currency(ctx.author.id, 'tokens', total_tokens)

        stats = await db.get_fishing_stats(ctx.author.id)
        await db.update_fishing_stats(ctx.author.id, total_value=stats['total_value'] + total_coins)

        summary = f"**+{total_coins:,}** 🪙"
        if total_gems:
            summary += f"  **+{total_gems}** 💎"
        if total_tokens:
            summary += f"  **+{total_tokens}** 🎫"

        body = "\n".join(sell_lines[:15])
        if len(sell_lines) > 15:
            body += f"\n*...and {len(sell_lines)-15} more*"

        embed = discord.Embed(title="💰 Fish Sold!", description=body or "Nothing sold.", color=config.COLORS['success'])
        embed.add_field(name="Total Earned", value=summary, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='fishstats', description='View your fishing statistics')
    async def fishstats(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        await db.ensure_user(target.id, target.name)
        await db.ensure_fishing_row(target.id)

        stats = await db.get_fishing_stats(target.id)
        inv = await db.get_inventory(target.id)
        rod_tier = _get_rod_tier_from_inventory(inv)
        rod_name = _get_rod_name_from_tier(rod_tier)

        fishing_level = _fishing_level_from_xp(stats['fishing_xp'])
        xp_now, xp_need = _xp_in_current_level(stats['fishing_xp'])
        filled = int(min(xp_now / xp_need, 1.0) * 12) if xp_need > 0 else 12
        bar = '█' * filled + '░' * (12 - filled)

        biggest = "None yet"
        if stats['biggest_catch_type']:
            fname = stats['biggest_catch_type'].replace('_', ' ').title()
            tier_key = get_tier_for_fish(fname)
            emoji = TIER_EMOJIS.get(tier_key or 'common', '🐟')
            biggest = f"{emoji} {fname} (~{stats['biggest_catch_coins']:,} 🪙)"

        bait = "Active ✅" if await _check_premium_bait(target.id) else "None"

        embed = discord.Embed(
            title=f"🎣 {target.display_name}'s Fishing Stats",
            color=config.COLORS['info'],
        )
        embed.add_field(name="Fishing Level", value=f"`{fishing_level}`", inline=True)
        embed.add_field(name="XP Progress", value=f"`{xp_now}/{xp_need}`\n`[{bar}]`", inline=True)
        embed.add_field(name="Current Rod", value=f"`{rod_name}` (Tier {rod_tier})", inline=True)
        embed.add_field(name="Total Caught", value=f"`{stats['total_caught']:,}`", inline=True)
        embed.add_field(name="Total Earned", value=f"`{stats['total_value']:,}` 🪙", inline=True)
        embed.add_field(name="Best Catch", value=biggest, inline=True)
        embed.add_field(name="Premium Bait", value=bait, inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="t!fish | t!sell all | t!rods | t!shop")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='rods', description='View all fishing rods and their requirements')
    async def rods(self, ctx: commands.Context):
        inv = await db.get_inventory(ctx.author.id)
        owned_keys = {row['item_key'] for row in inv}
        current_rod_tier = _get_rod_tier_from_inventory(inv)

        embed = discord.Embed(
            title="🎣 Fishing Rods",
            description="Higher tier rods reduce cooldown and unlock rarer fish tiers.",
            color=config.COLORS['primary'],
        )
        for rod_key, rod_info in RODS.items():
            tier = rod_info['tier']
            owned = rod_key in owned_keys or tier == 0
            status = "✅ Equipped" if tier == current_rod_tier else ("✅ Owned" if owned else "🔒 Locked")

            price_str = ""
            if rod_info['price_coins']:
                price_str += f"{rod_info['price_coins']:,} 🪙 "
            if rod_info['price_gems']:
                price_str += f"{rod_info['price_gems']} 💎 "
            if rod_info['price_tokens']:
                price_str += f"{rod_info['price_tokens']} 🎫"
            if not price_str:
                price_str = "Free"

            # Unlocks tier info
            catchable = []
            for tk, ti in TIERS.items():
                if ti['min_rod'] <= tier:
                    catchable.append(ti['label'])
            unlock_str = ", ".join(catchable[-3:]) if catchable else "Basic only"

            embed.add_field(
                name=f"Tier {tier} — {rod_info['name']} {status}",
                value=(
                    f"*{rod_info['description']}*\n"
                    f"Cooldown: `{rod_info['cooldown']}s` | Price: `{price_str}`\n"
                    f"Unlocks: `{unlock_str}`"
                ),
                inline=False,
            )
        embed.set_footer(text="Buy rods with t!buy <rod_key> | e.g. t!buy rod_pearl")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='fishtop', aliases=['fishlb'], description='Fishing leaderboard')
    async def fishtop(self, ctx: commands.Context):
        rows = await db.get_fishing_leaderboard(limit=10)
        if not rows:
            await ctx.send(embed=discord.Embed(
                description="No fishing data yet! Use `t!fish` then `t!sell all`.",
                color=config.COLORS['warning'],
            ))
            return

        medals = [':first_place:', ':second_place:', ':third_place:']
        lines = []
        for i, row in enumerate(rows):
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            member = ctx.guild.get_member(row['user_id']) if ctx.guild else None
            name = member.display_name if member else (row['username'] or f"User {row['user_id']}")
            lines.append(
                f"{medal} **{name}** — `{row['total_caught']:,}` caught · `{row['total_value']:,}` 🪙"
            )

        embed = discord.Embed(
            title="🎣 Fishing Leaderboard",
            description="\n".join(lines),
            color=config.COLORS['gold'],
        )
        embed.set_footer(text="Ranked by total coins earned from selling fish")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fishing(bot))
