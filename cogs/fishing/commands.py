"""
cogs/fishing/commands.py — Fishing cog.

Phase 3d: extracted verbatim from cogs/fishing/__init__.py. Slash + prefix
commands live here. Helpers are in service.py; tier rewards/colors in
constants.py; the static FISH/TIERS/RODS registry in data.py.
"""
import discord
from discord.ext import commands
import random
import aiosqlite
from datetime import datetime, timezone, timedelta
import logging

import config
import database as db

from .data import FISH, TIERS, RODS, get_rod_info, get_catchable_tiers, get_tier_for_fish
from .constants import TIER_EMOJIS, TIER_COLORS, TIER_XP, TIER_GEMS, TIER_TOKENS
from .service import *  # noqa: F401, F403  (re-exports the 9 helpers)

logger = logging.getLogger("tainment.fishing.commands")


# ─── Fishing cog ────────────────────────────────────────────────────────────

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
        fishing_level = _fishing_level_from_xp(stats['fishing_xp'])
        equipped_rod = stats['equipped_rod'] if stats and 'equipped_rod' in stats.keys() else None
        rod_tier = _get_rod_tier_from_inventory(inv, equipped_rod, fishing_level)
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

        # Fish Vacuum: auto-discard all trash fish from bag, consume item
        vacuum_note = ""
        if await db.has_active_item(ctx.author.id, 'fish_vacuum'):
            fish_bag = await db.get_fish_inventory(ctx.author.id)
            vacuumed = 0
            for row in fish_bag:
                fname = row['fish_key'].replace('_', ' ').title()
                if get_tier_for_fish(fname) == 'trash':
                    vacuumed += row['quantity']
                    await db.sell_fish_from_bag(ctx.author.id, row['fish_key'], row['quantity'])
            await db.remove_inventory_item(ctx.author.id, 'fish_vacuum')
            if vacuumed:
                vacuum_note = f"\n🧹 **Fish Vacuum:** Auto-discarded {vacuumed} trash fish."

        tier_info = TIERS.get(tier_key, {})
        tier_label = tier_info.get('label', tier_key.title())
        emoji = TIER_EMOJIS.get(tier_key, '🐟')
        color = TIER_COLORS.get(tier_key, config.COLORS['primary'])
        rod_name = _get_rod_name_from_tier(rod_tier)

        if tier_key == 'trash':
            title = f"Reeled in... {emoji} {fish_name}"
            desc = vacuum_note.strip() if vacuum_note else f"*This is just junk.* Discard with `t!sell all`."
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
            if vacuum_note:
                desc += vacuum_note
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
        fishing_level = _fishing_level_from_xp(stats['fishing_xp'])
        equipped_rod = stats['equipped_rod'] if stats and 'equipped_rod' in stats.keys() else None
        rod_tier = _get_rod_tier_from_inventory(inv, equipped_rod, fishing_level)
        rod_name = _get_rod_name_from_tier(rod_tier)
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
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_fishing_row(ctx.author.id)
        stats = await db.get_fishing_stats(ctx.author.id)
        inv = await db.get_inventory(ctx.author.id)
        fishing_level = _fishing_level_from_xp(stats['fishing_xp'])
        raw_owned = {row['item_key'] for row in inv}
        owned_keys = {k[4:] if k.startswith('rod_') else k for k in raw_owned}
        equipped_rod = stats['equipped_rod'] if stats and 'equipped_rod' in stats.keys() else None
        current_rod_tier = _get_rod_tier_from_inventory(inv, equipped_rod, fishing_level)

        embed = discord.Embed(
            title="🎣 Fishing Rods",
            description=f"Your Fishing Level: **{fishing_level}**\nHigher tier rods unlock rarer fish and shorter cooldowns.\nUse `t!equip <rod_key>` to switch rods.",
            color=config.COLORS['primary'],
        )
        for rod_key, rod_info in RODS.items():
            tier = rod_info['tier']
            min_level = rod_info.get('min_level', 1)
            owned = rod_key in owned_keys or tier == 0
            level_ok = fishing_level >= min_level
            is_equipped = tier == current_rod_tier and owned and level_ok

            if is_equipped:
                status = "🎣 Equipped"
            elif owned and level_ok:
                status = "✅ Owned"
            elif owned and not level_ok:
                status = f"🔒 Owned (need Lvl {min_level})"
            else:
                status = "🔒 Buy"

            price_str = ""
            if rod_info['price_coins']:
                price_str += f"{rod_info['price_coins']:,} 🪙 "
            if rod_info['price_gems']:
                price_str += f"{rod_info['price_gems']} 💎 "
            if rod_info['price_tokens']:
                price_str += f"{rod_info['price_tokens']} 🎫"
            if not price_str:
                price_str = "Free"

            catchable = []
            for tk, ti in TIERS.items():
                if ti['min_rod'] <= tier:
                    catchable.append(ti['label'])
            unlock_str = ", ".join(catchable[-3:]) if catchable else "Basic only"

            lvl_str = "No req." if min_level <= 1 else f"Level {min_level}"
            embed.add_field(
                name=f"Tier {tier} — {rod_info['name']} {status}",
                value=(
                    f"*{rod_info['desc']}*\n"
                    f"Req: `{lvl_str}` | Cooldown: `{rod_info['cooldown']}s` | Price: `{price_str}`\n"
                    f"Unlocks: `{unlock_str}` | Key: `{rod_key}`"
                ),
                inline=False,
            )
        embed.set_footer(text=f"Fishing Lvl {fishing_level} | t!equip <rod_key> | t!unequip to auto-select")
        await ctx.send(embed=embed)

    @commands.command(name='radar', description='Use your Fish Radar to preview your next 5 catches')
    async def radar(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_fishing_row(ctx.author.id)

        removed = await db.remove_inventory_item(ctx.author.id, 'fishing_radar')
        if not removed:
            await ctx.send(embed=discord.Embed(
                description="You don't have a **Fish Radar**. Buy one with `t!buy fishing_radar` (15 💎).",
                color=config.COLORS['error'],
            ))
            return

        stats = await db.get_fishing_stats(ctx.author.id)
        inv = await db.get_inventory(ctx.author.id)
        fishing_level = _fishing_level_from_xp(stats['fishing_xp'])
        equipped_rod = stats['equipped_rod'] if stats and 'equipped_rod' in stats.keys() else None
        rod_tier = _get_rod_tier_from_inventory(inv, equipped_rod, fishing_level)
        bait_active = await _check_premium_bait(ctx.author.id)
        sub_tier = await db.get_tier(ctx.author.id)

        lines = []
        for i in range(5):
            tier_key, fish_name, min_c, max_c = _pick_fish(rod_tier, fishing_level, bait_active, sub_tier)
            emoji = TIER_EMOJIS.get(tier_key, '🐟')
            tier_label = TIERS.get(tier_key, {}).get('label', tier_key.title())
            val_str = f"~{random.randint(min_c, max_c):,} 🪙" if max_c > 0 else "No sell value"
            lines.append(f"`{i + 1}.` {emoji} **{fish_name}** — {tier_label} ({val_str})")

        rod_name = _get_rod_name_from_tier(rod_tier)
        embed = discord.Embed(
            title="📡 Fish Radar — Next 5 Catches",
            description="\n".join(lines),
            color=config.COLORS['info'],
        )
        embed.set_footer(text=f"Rod: {rod_name} (Tier {rod_tier})  |  Fishing Lvl {fishing_level}  |  Radar consumed")
        await ctx.send(embed=embed)

    @commands.command(name='equip', description='Equip a fishing rod you own')
    async def equip(self, ctx: commands.Context, rod_key: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_fishing_row(ctx.author.id)

        rod_key = rod_key.lower()
        if rod_key not in RODS:
            valid = ', '.join(f'`{k}`' for k in RODS.keys())
            await ctx.send(embed=discord.Embed(
                description=f"Unknown rod key. Valid rods: {valid}",
                color=config.COLORS['error'],
            ))
            return

        rod_info = RODS[rod_key]
        min_level = rod_info.get('min_level', 1)

        # Tier 0 rod (starter) is always available; others need ownership + level check
        if rod_info['tier'] > 0:
            inv = await db.get_inventory(ctx.author.id)
            owned_keys = {row['item_key'] for row in inv}
            if rod_key not in owned_keys and f'rod_{rod_key}' not in owned_keys:
                await ctx.send(embed=discord.Embed(
                    description=f"You don't own **{rod_info['name']}**. Buy it with `t!buy rod_{rod_key}`.",
                    color=config.COLORS['error'],
                ))
                return

        # Level requirement check
        if min_level > 1:
            stats = await db.get_fishing_stats(ctx.author.id)
            fishing_level = _fishing_level_from_xp(stats['fishing_xp'])
            if fishing_level < min_level:
                await ctx.send(embed=discord.Embed(
                    description=(
                        f"**{rod_info['name']}** requires **Fishing Level {min_level}**.\n"
                        f"You're currently **Level {fishing_level}**. Keep fishing to level up!"
                    ),
                    color=config.COLORS['error'],
                ))
                return

        await db.update_fishing_stats(ctx.author.id, equipped_rod=rod_key)
        embed = discord.Embed(
            title="🎣 Rod Equipped",
            description=f"You equipped **{rod_info['name']}** (Tier {rod_info['tier']}).\nCooldown: `{rod_info['cooldown']}s`",
            color=config.COLORS['success'],
        )
        await ctx.send(embed=embed)

    @commands.command(name='unequip', description='Unequip rod — auto-selects your best owned rod')
    async def unequip(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_fishing_row(ctx.author.id)
        await db.update_fishing_stats(ctx.author.id, equipped_rod=None)
        await ctx.send(embed=discord.Embed(
            description="Rod unequipped. Your best owned rod will be used automatically.",
            color=config.COLORS['success'],
        ))

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


# ─── Setup ──────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(Fishing(bot))
