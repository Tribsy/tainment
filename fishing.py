"""
Competitive fishing game.
Commands: fish, fishbag, sell, fishstats, fishtop
Fish can be sold for coins + gems + tokens depending on rarity.
Fishing rods (rod_silver / rod_gold / rod_diamond) from the shop improve catch rates.
"""

import discord
from discord.ext import commands
import random
from datetime import datetime, timezone
import config
import database as db

# ── Fish catalogue ─────────────────────────────────────────────────────────────
# min/max_coins = sell value per fish
# gems/tokens   = bonus currencies on sell
# xp            = fishing XP gained on catch
# weight        = rarity weight (higher = more common)

FISH_CATALOG: dict[str, dict] = {
    # Common (~54%)
    'sardine':      {'name': 'Sardine',       'emoji': '🐟', 'tier': 'Common',    'min_coins': 5,    'max_coins': 15,   'gems': 0,  'tokens': 0, 'xp': 10,  'weight': 250},
    'herring':      {'name': 'Herring',       'emoji': '🐟', 'tier': 'Common',    'min_coins': 8,    'max_coins': 20,   'gems': 0,  'tokens': 0, 'xp': 10,  'weight': 220},
    'mackerel':     {'name': 'Mackerel',      'emoji': '🐠', 'tier': 'Common',    'min_coins': 10,   'max_coins': 25,   'gems': 0,  'tokens': 0, 'xp': 12,  'weight': 190},
    'carp':         {'name': 'Carp',          'emoji': '🐡', 'tier': 'Common',    'min_coins': 12,   'max_coins': 30,   'gems': 0,  'tokens': 0, 'xp': 12,  'weight': 210},
    # Uncommon (~27%)
    'bass':         {'name': 'Bass',          'emoji': '🐠', 'tier': 'Uncommon',  'min_coins': 30,   'max_coins': 60,   'gems': 0,  'tokens': 0, 'xp': 25,  'weight': 130},
    'trout':        {'name': 'Trout',         'emoji': '🐟', 'tier': 'Uncommon',  'min_coins': 35,   'max_coins': 70,   'gems': 0,  'tokens': 0, 'xp': 28,  'weight': 120},
    'catfish':      {'name': 'Catfish',       'emoji': '🐡', 'tier': 'Uncommon',  'min_coins': 40,   'max_coins': 80,   'gems': 0,  'tokens': 0, 'xp': 30,  'weight': 110},
    'pike':         {'name': 'Pike',          'emoji': '🐠', 'tier': 'Uncommon',  'min_coins': 45,   'max_coins': 90,   'gems': 0,  'tokens': 0, 'xp': 33,  'weight': 100},
    # Rare (~8%)
    'salmon':       {'name': 'Salmon',        'emoji': '🐟', 'tier': 'Rare',      'min_coins': 80,   'max_coins': 160,  'gems': 1,  'tokens': 0, 'xp': 60,  'weight': 55},
    'tuna':         {'name': 'Tuna',          'emoji': '🐠', 'tier': 'Rare',      'min_coins': 100,  'max_coins': 200,  'gems': 1,  'tokens': 0, 'xp': 70,  'weight': 40},
    'swordfish':    {'name': 'Swordfish',     'emoji': '🐟', 'tier': 'Rare',      'min_coins': 150,  'max_coins': 300,  'gems': 2,  'tokens': 1, 'xp': 85,  'weight': 28},
    'shark':        {'name': 'Shark',         'emoji': '🦈', 'tier': 'Rare',      'min_coins': 200,  'max_coins': 400,  'gems': 2,  'tokens': 1, 'xp': 100, 'weight': 17},
    # Legendary (~0.6%)
    'golden_fish':  {'name': 'Golden Fish',   'emoji': '✨', 'tier': 'Legendary', 'min_coins': 500,  'max_coins': 1000, 'gems': 5,  'tokens': 2, 'xp': 150, 'weight': 5},
    'ancient_carp': {'name': 'Ancient Carp',  'emoji': '🏺', 'tier': 'Legendary', 'min_coins': 750,  'max_coins': 1500, 'gems': 8,  'tokens': 3, 'xp': 200, 'weight': 3},
    'kraken_jr':    {'name': 'Kraken Jr',     'emoji': '🦑', 'tier': 'Legendary', 'min_coins': 1000, 'max_coins': 2000, 'gems': 12, 'tokens': 5, 'xp': 300, 'weight': 2},
    # Junk (~3.5%)
    'old_boot':     {'name': 'Old Boot',      'emoji': '👟', 'tier': 'Junk',      'min_coins': 0,    'max_coins': 0,    'gems': 0,  'tokens': 0, 'xp': 2,   'weight': 70},
    'seaweed':      {'name': 'Seaweed',       'emoji': '🌿', 'tier': 'Junk',      'min_coins': 0,    'max_coins': 0,    'gems': 0,  'tokens': 0, 'xp': 2,   'weight': 65},
    # Special (~0.6%)
    'treasure':     {'name': 'Treasure Chest','emoji': '🎁', 'tier': 'Special',   'min_coins': 200,  'max_coins': 500,  'gems': 3,  'tokens': 1, 'xp': 40,  'weight': 11},
}

TIER_COLORS = {
    'Common':    0x95a5a6,
    'Uncommon':  0x2ecc71,
    'Rare':      0x3498db,
    'Legendary': 0xf39c12,
    'Special':   0x9b59b6,
    'Junk':      0x7f8c8d,
}

BASE_COOLDOWN = 15  # seconds
ROD_COOLDOWN = {
    'rod_silver':  12,
    'rod_gold':    10,
    'rod_diamond': 7,
}

# Rod tier weight multipliers per fish tier
ROD_MULT: dict[str | None, dict] = {
    None:          {},
    'rod_silver':  {'Uncommon': 1.3, 'Rare': 1.5, 'Junk': 0.6},
    'rod_gold':    {'Uncommon': 1.6, 'Rare': 2.2, 'Legendary': 1.5, 'Junk': 0.3},
    'rod_diamond': {'Uncommon': 2.0, 'Rare': 3.5, 'Legendary': 3.0, 'Special': 2.0, 'Junk': 0.05},
}


def _best_rod(inventory_rows) -> str | None:
    """Return key of the best rod the user owns."""
    owned = {row['item_key'] for row in inventory_rows}
    for rod in ('rod_diamond', 'rod_gold', 'rod_silver'):
        if rod in owned:
            return rod
    return None


def _pick_fish(rod_key: str | None, fishing_level: int) -> str:
    """Pick a random fish key with rod/level-adjusted weights."""
    keys = list(FISH_CATALOG.keys())
    base_weights = [FISH_CATALOG[k]['weight'] for k in keys]

    mult = dict(ROD_MULT.get(rod_key, {}))

    # Fishing level bonus: every 5 levels +10% rare/legendary
    level_bonus = min(fishing_level // 5, 6) * 0.10
    if level_bonus > 0:
        for tier in ('Rare', 'Legendary'):
            mult[tier] = mult.get(tier, 1.0) * (1 + level_bonus)

    adjusted = [w * mult.get(FISH_CATALOG[k]['tier'], 1.0) for k, w in zip(keys, base_weights)]
    return random.choices(keys, weights=adjusted, k=1)[0]


def _xp_for_level(level: int) -> int:
    """XP needed to complete a given level."""
    needed = 100
    for _ in range(level):
        needed = int(needed * 1.4)
    return needed


def _fishing_level_from_xp(total_xp: int) -> int:
    level, remaining = 0, total_xp
    while True:
        needed = _xp_for_level(level)
        if remaining < needed:
            break
        remaining -= needed
        level += 1
    return level


def _xp_in_current_level(total_xp: int) -> tuple[int, int]:
    """Returns (xp_into_level, xp_needed_for_level)."""
    level = 0
    remaining = total_xp
    while True:
        needed = _xp_for_level(level)
        if remaining < needed:
            return remaining, needed
        remaining -= needed
        level += 1


# ── Fishing Cog ───────────────────────────────────────────────────────────────

class Fishing(commands.Cog, name="Fishing"):
    """Competitive fishing game with 18 fish types and rod upgrades."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='fish', description='Cast your line and catch a fish!')
    async def fish(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await db.ensure_fishing_row(ctx.author.id)

        stats = await db.get_fishing_stats(ctx.author.id)
        inv = await db.get_inventory(ctx.author.id)
        rod_key = _best_rod(inv)
        cooldown = ROD_COOLDOWN.get(rod_key, BASE_COOLDOWN)

        # Cooldown check
        if stats['last_fished']:
            last_dt = datetime.fromisoformat(stats['last_fished']).replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if elapsed < cooldown:
                remaining = cooldown - elapsed
                await ctx.send(embed=discord.Embed(
                    title="Line not ready!",
                    description=f"Your line resets in **{remaining:.0f}s**.",
                    color=config.COLORS['warning'],
                ))
                return

        fishing_level = _fishing_level_from_xp(stats['fishing_xp'])
        fish_key = _pick_fish(rod_key, fishing_level)
        fish = FISH_CATALOG[fish_key]
        coins = random.randint(fish['min_coins'], fish['max_coins']) if fish['max_coins'] > 0 else 0

        # Update DB
        await db.add_fish_to_bag(ctx.author.id, fish_key)
        new_xp = stats['fishing_xp'] + fish['xp']
        new_level = _fishing_level_from_xp(new_xp)

        biggest_coins = stats['biggest_catch_coins'] or 0
        new_biggest_type = stats['biggest_catch_type']
        if coins > biggest_coins:
            biggest_coins = coins
            new_biggest_type = fish_key

        await db.update_fishing_stats(
            ctx.author.id,
            total_caught=stats['total_caught'] + 1,
            fishing_xp=new_xp,
            fishing_level=new_level,
            last_fished=datetime.now(timezone.utc).isoformat(),
            biggest_catch_type=new_biggest_type,
            biggest_catch_coins=biggest_coins,
        )

        tier = fish['tier']
        color = TIER_COLORS.get(tier, config.COLORS['primary'])
        rod_str = f" [{rod_key.replace('rod_', '').title()} Rod]" if rod_key else ""

        if tier == 'Junk':
            title = f"You caught... {fish['emoji']} {fish['name']}"
            desc = "Nothing useful here. Discard with `t!sell all`."
        else:
            val_str = f"Worth ~**{coins:,}** \U0001fa99 when sold"
            extras = ""
            if fish['gems']:
                extras += f" + **{fish['gems']}** \U0001f48e"
            if fish['tokens']:
                extras += f" + **{fish['tokens']}** \U0001f3ab"
            desc = f"{val_str}{extras}\n*Tier: **{tier}***  |  XP: `+{fish['xp']}`"
            if new_level > fishing_level:
                desc += f"\n\n\U0001f389 **Fishing Level Up! Now level {new_level}!**"
            desc += f"\n\nSell: `t!sell {fish_key}` or `t!sell all`"
            title = f"Caught {fish['emoji']} {fish['name']}!{rod_str}"

        xp_now, xp_need = _xp_in_current_level(new_xp)
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_footer(
            text=f"Fishing Lvl {new_level}  |  {stats['total_caught']+1} total catches  "
                 f"|  XP {xp_now}/{xp_need}  |  Cooldown {cooldown}s"
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

        lines = []
        total_est = 0
        for row in fish_inv:
            fdata = FISH_CATALOG.get(row['fish_key'])
            if not fdata:
                continue
            qty = row['quantity']
            avg = (fdata['min_coins'] + fdata['max_coins']) // 2
            est = avg * qty
            total_est += est
            lines.append(f"{fdata['emoji']} **{fdata['name']}** \u00d7{qty}  ~`{est:,}` \U0001fa99")

        embed = discord.Embed(
            title=f"\U0001f3a3 {target.display_name}'s Fish Bag",
            description="\n".join(lines),
            color=config.COLORS['primary'],
        )
        embed.set_footer(text=f"Est. sell value: ~{total_est:,} coins  |  t!sell all to cash out")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='sell', description='Sell fish from your bag (sell <fish_key|all>)')
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
                names = ', '.join(f"`{r['fish_key']}`" for r in fish_inv)
                await ctx.send(embed=discord.Embed(
                    description=f"You don't have `{target_fish}`. Bag: {names}",
                    color=config.COLORS['error'],
                ))
                return

        total_coins, total_gems, total_tokens = 0, 0, 0
        sell_lines = []

        for fkey, qty in to_sell.items():
            fdata = FISH_CATALOG.get(fkey)
            if not fdata:
                continue
            await db.sell_fish_from_bag(ctx.author.id, fkey, qty)
            if fdata['tier'] == 'Junk':
                sell_lines.append(f"{fdata['emoji']} {fdata['name']} \u00d7{qty} \u2192 junk (0 \U0001fa99)")
                continue
            coins = sum(random.randint(fdata['min_coins'], fdata['max_coins']) for _ in range(qty))
            gems = fdata['gems'] * qty
            tokens = fdata['tokens'] * qty
            total_coins += coins
            total_gems += gems
            total_tokens += tokens
            val = f"**{coins:,}** \U0001fa99"
            if gems:
                val += f" + **{gems}** \U0001f48e"
            if tokens:
                val += f" + **{tokens}** \U0001f3ab"
            sell_lines.append(f"{fdata['emoji']} {fdata['name']} \u00d7{qty} \u2192 {val}")

        if total_coins > 0:
            await db.earn_currency(ctx.author.id, 'coins', total_coins)
        if total_gems > 0:
            await db.earn_currency(ctx.author.id, 'gems', total_gems)
        if total_tokens > 0:
            await db.earn_currency(ctx.author.id, 'tokens', total_tokens)

        stats = await db.get_fishing_stats(ctx.author.id)
        await db.update_fishing_stats(ctx.author.id, total_value=stats['total_value'] + total_coins)

        summary = f"**+{total_coins:,}** \U0001fa99"
        if total_gems:
            summary += f"  **+{total_gems}** \U0001f48e"
        if total_tokens:
            summary += f"  **+{total_tokens}** \U0001f3ab"

        body = "\n".join(sell_lines[:15])
        if len(sell_lines) > 15:
            body += f"\n*...and {len(sell_lines)-15} more*"

        embed = discord.Embed(title="\U0001f4b0 Fish Sold!", description=body, color=config.COLORS['success'])
        embed.add_field(name="Total Earned", value=summary, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='fishstats', description='View your fishing statistics')
    async def fishstats(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        await db.ensure_user(target.id, target.name)
        await db.ensure_fishing_row(target.id)

        stats = await db.get_fishing_stats(target.id)
        fish_inv = await db.get_fish_inventory(target.id)

        fishing_level = _fishing_level_from_xp(stats['fishing_xp'])
        xp_now, xp_need = _xp_in_current_level(stats['fishing_xp'])
        filled = int(min(xp_now / xp_need, 1.0) * 10) if xp_need > 0 else 10
        bar = '\u2588' * filled + '\u2591' * (10 - filled)

        biggest = "None yet"
        if stats['biggest_catch_type'] and stats['biggest_catch_type'] in FISH_CATALOG:
            f = FISH_CATALOG[stats['biggest_catch_type']]
            biggest = f"{f['emoji']} {f['name']} (~{stats['biggest_catch_coins']:,} \U0001fa99)"

        bag_preview = [
            f"{FISH_CATALOG[r['fish_key']]['emoji']} {FISH_CATALOG[r['fish_key']]['name']} \u00d7{r['quantity']}"
            for r in fish_inv if r['fish_key'] in FISH_CATALOG
        ][:5]

        embed = discord.Embed(
            title=f"\U0001f3a3 {target.display_name}'s Fishing Stats",
            color=config.COLORS['info'],
        )
        embed.add_field(name="Fishing Level", value=f"`{fishing_level}`", inline=True)
        embed.add_field(name="XP Progress", value=f"`{xp_now}/{xp_need}` [{bar}]", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Total Caught", value=f"`{stats['total_caught']:,}`", inline=True)
        embed.add_field(name="Total Sold For", value=f"`{stats['total_value']:,}` \U0001fa99", inline=True)
        embed.add_field(name="Best Catch", value=biggest, inline=True)
        if bag_preview:
            embed.add_field(name="In Bag", value="\n".join(bag_preview), inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="t!fish to catch  |  t!sell all to cash out  |  t!shop for rods")
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
                f"{medal} **{name}** — `{row['total_caught']:,}` caught · `{row['total_value']:,}` \U0001fa99"
            )

        embed = discord.Embed(
            title="\U0001f3a3 Fishing Leaderboard",
            description="\n".join(lines),
            color=config.COLORS['gold'],
        )
        embed.set_footer(text="Ranked by total coins earned from selling fish")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fishing(bot))
