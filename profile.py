import discord
from discord.ext import commands
from datetime import datetime, timezone
import aiosqlite
import config
import database as db
from levels import xp_for_next, total_xp_for_level


TIER_COLORS = {
    'Basic': config.COLORS['info'],
    'Vibe': 0xe040fb,
    'Premium': config.COLORS['gold'],
    'Pro': config.COLORS['purple'],
}

TIER_BADGES = {
    'Basic': '',
    'Vibe': ' \U0001f525 Vibe',
    'Premium': ' \u2b50 Premium',
    'Pro': ' \u26a1 Pro',
}

# Banner item -> embed color
BANNER_COLORS = {
    'profile_banner_blue':   0x1a6fa3,
    'profile_banner_red':    0xc0392b,
    'profile_banner_gold':   0xf1c40f,
    'profile_banner_purple': 0x9b59b6,
    'profile_banner_void':   0x1a1a2e,
}

# Frame item -> label shown on profile
FRAME_LABELS = {
    'profile_frame_gold':   '\u2b50 Gold Frame',
    'profile_frame_cosmic': '\U0001f30c Cosmic Frame',
}


class Profile(commands.Cog, name="Profile"):
    """User profile cards with stats."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='profile', aliases=['me', 'card'], description='View your profile card')
    async def profile(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        await db.ensure_user(target.id, target.name)

        tier = await db.get_tier(target.id)
        eco = await db.get_economy(target.id)
        coins = eco['coins'] if eco else 0
        total_earned = eco['total_earned'] if eco else 0
        streak = eco['daily_streak'] if eco else 0

        # Level data
        level_data = None
        level = 0
        xp = 0
        if ctx.guild:
            level_data = await db.get_level_data(target.id, ctx.guild.id)
            if level_data:
                level = level_data['level']
                xp = level_data['xp']

        # Game scores
        async with aiosqlite.connect(config.DB_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute(
                "SELECT COUNT(*) as games, SUM(score) as total FROM game_scores WHERE user_id = ?",
                (target.id,)
            ) as cur:
                game_row = await cur.fetchone()

            async with db_conn.execute(
                "SELECT tier FROM subscriptions WHERE user_id = ?", (target.id,)
            ) as cur:
                sub = await cur.fetchone()

            # Inventory highlights
            async with db_conn.execute("""
                SELECT item_key FROM inventory
                WHERE user_id = ?
                AND (expires_at IS NULL OR expires_at > datetime('now'))
            """, (target.id,)) as cur:
                active_items = [r['item_key'] for r in await cur.fetchall()]

        games_played = game_row['games'] if game_row and game_row['games'] else 0
        total_score = game_row['total'] if game_row and game_row['total'] else 0
        has_vip = 'vip_badge' in active_items

        # Profile customization from inventory
        banner_color = TIER_COLORS.get(tier, config.COLORS['primary'])
        for banner_key, banner_clr in BANNER_COLORS.items():
            if banner_key in active_items:
                banner_color = banner_clr
                break

        frame_label = ''
        for frame_key, flabel in FRAME_LABELS.items():
            if frame_key in active_items:
                frame_label = f' {flabel}'
                break

        has_prestige = 'prestige_badge' in active_items
        badge = TIER_BADGES.get(tier, '')
        vip_badge = ' \U0001f451 VIP' if has_vip else ''
        prestige_badge = ' \u2728 Prestige' if has_prestige else ''

        # Fetch bio
        async with aiosqlite.connect(config.DB_PATH) as _db:
            async with _db.execute("SELECT bio FROM users WHERE user_id = ?", (target.id,)) as _cur:
                _bio_row = await _cur.fetchone()
        bio_text = _bio_row[0] if _bio_row and _bio_row[0] else None

        embed = discord.Embed(
            title=f"{target.display_name}{badge}{vip_badge}{prestige_badge}",
            color=banner_color,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        desc_parts = []
        if frame_label:
            desc_parts.append(f"*{frame_label}*")
        if bio_text:
            desc_parts.append(bio_text)
        if desc_parts:
            embed.description = "\n".join(desc_parts)

        # Level progress bar
        if ctx.guild and level_data:
            needed = xp_for_next(level)
            progress_xp = xp - total_xp_for_level(level)
            pct = min(1.0, progress_xp / needed) if needed else 1.0
            filled = int(20 * pct)
            bar = '█' * filled + '░' * (20 - filled)
            level_str = f"Level `{level}` — `{bar}` {int(pct*100)}%\n`{progress_xp:,}` / `{needed:,}` XP"
        else:
            level_str = "`No XP data for this server`"

        embed.add_field(name="Level", value=level_str, inline=False)

        # Economy
        gems = eco['gems'] if eco else 0
        tokens = eco['tokens'] if eco else 0
        embed.add_field(name="\U0001fa99 Coins", value=f"`{coins:,}`", inline=True)
        embed.add_field(name="\U0001f48e Gems", value=f"`{gems:,}`", inline=True)
        embed.add_field(name="\U0001f3ab Tokens", value=f"`{tokens:,}`", inline=True)
        embed.add_field(name="Daily Streak", value=f"`{streak}` days", inline=True)
        embed.add_field(name="Tier", value=f"**{tier}**", inline=True)
        embed.add_field(name="Total Earned", value=f"`{total_earned:,}` \U0001fa99", inline=True)

        embed.add_field(name="Games Played", value=f"`{games_played}`", inline=True)
        embed.add_field(name="Total Score", value=f"`{total_score:,}`", inline=True)

        # Fishing stats
        async with aiosqlite.connect(config.DB_PATH) as db_conn:
            async with db_conn.execute(
                "SELECT fishing_level, total_caught, total_value FROM fishing_stats WHERE user_id=?",
                (target.id,)
            ) as cur:
                fish_row = await cur.fetchone()
        if fish_row and fish_row[1] > 0:
            embed.add_field(
                name="\U0001f3a3 Fishing",
                value=f"Level `{fish_row[0]}` | `{fish_row[1]:,}` caught | `{fish_row[2]:,}` \U0001fa99 earned",
                inline=False,
            )

        if active_items:
            from shop import SHOP
            item_names = []
            for key in active_items:
                item_data = SHOP.get(key) or config.SHOP_ITEMS.get(key)
                if item_data:
                    item_names.append(item_data['name'])
            if item_names:
                embed.add_field(name="Active Items", value=', '.join(item_names[:8]), inline=False)

        # Member since
        if hasattr(target, 'joined_at') and target.joined_at:
            ts = int(target.joined_at.timestamp())
            embed.add_field(name="Joined Server", value=f"<t:{ts}:R>", inline=True)

        embed.set_footer(text=f"Tainment+ v{config.BOT_VERSION}")
        await ctx.send(embed=embed)

    @commands.command(name='serverinfo', description='View server information')
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        embed = discord.Embed(title=guild.name, color=config.COLORS['primary'])
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="Members", value=f"`{guild.member_count:,}`", inline=True)
        embed.add_field(name="Channels", value=f"`{len(guild.channels)}`", inline=True)
        embed.add_field(name="Roles", value=f"`{len(guild.roles)}`", inline=True)
        embed.add_field(name="Boosts", value=f"`{guild.premium_subscription_count}`", inline=True)
        embed.add_field(name="Boost Level", value=f"`{guild.premium_tier}`", inline=True)

        ts = int(guild.created_at.timestamp())
        embed.add_field(name="Created", value=f"<t:{ts}:D>", inline=True)

        if guild.description:
            embed.add_field(name="Description", value=guild.description, inline=False)

        embed.set_footer(text=f"ID: {guild.id}")
        await ctx.send(embed=embed)

    @commands.command(name='userinfo', description='View info about a user')
    async def userinfo(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        embed = discord.Embed(
            title=str(target),
            description=target.mention,
            color=config.COLORS['primary'],
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Display Name", value=target.display_name, inline=True)
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)

        ts_created = int(target.created_at.timestamp())
        embed.add_field(name="Account Created", value=f"<t:{ts_created}:R>", inline=True)

        if hasattr(target, 'joined_at') and target.joined_at:
            ts_joined = int(target.joined_at.timestamp())
            embed.add_field(name="Joined Server", value=f"<t:{ts_joined}:R>", inline=True)

        if hasattr(target, 'roles'):
            roles = [r.mention for r in reversed(target.roles) if r.name != '@everyone']
            if roles:
                embed.add_field(
                    name=f"Roles ({len(roles)})",
                    value=' '.join(roles[:10]) + ('...' if len(roles) > 10 else ''),
                    inline=False,
                )

        embed.set_footer(text=f"ID: {target.id}")
        await ctx.send(embed=embed)

    @commands.command(name='avatar', aliases=['av', 'pfp'], description="View a user's avatar")
    async def avatar(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        embed = discord.Embed(
            title=f"{target.display_name}'s Avatar",
            color=config.COLORS['primary'],
        )
        embed.set_image(url=target.display_avatar.url)
        await ctx.send(embed=embed)


    @commands.command(name='bio', description='Set a custom bio on your profile (Vibe+)')
    async def bio(self, ctx: commands.Context, *, text: str = None):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        tier_order = ['Basic', 'Vibe', 'Premium', 'Pro']
        if tier_order.index(tier) < tier_order.index('Vibe'):
            await ctx.send(embed=discord.Embed(
                title="Vibe Required",
                description="Setting a bio requires a **Vibe** or higher subscription.\nUse `t!subscribe` to upgrade.",
                color=config.COLORS['warning'],
            ))
            return

        if not text:
            async with aiosqlite.connect(config.DB_PATH) as db_conn:
                async with db_conn.execute("SELECT bio FROM users WHERE user_id = ?", (ctx.author.id,)) as cur:
                    row = await cur.fetchone()
            current = row[0] if row and row[0] else "*No bio set.*"
            await ctx.send(embed=discord.Embed(
                title="Your Bio",
                description=current,
                color=config.COLORS['primary'],
            ))
            return

        if len(text) > 150:
            await ctx.send(embed=discord.Embed(
                description="Bio must be 150 characters or fewer.",
                color=config.COLORS['error'],
            ))
            return

        async with aiosqlite.connect(config.DB_PATH) as db_conn:
            await db_conn.execute("UPDATE users SET bio = ? WHERE user_id = ?", (text, ctx.author.id))
            await db_conn.commit()

        await ctx.send(embed=discord.Embed(
            title="Bio Updated",
            description=text,
            color=config.COLORS['success'],
        ))

    @commands.command(name='mystats', description='View your detailed personal stats (Premium+)')
    async def mystats(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        tier_order = ['Basic', 'Vibe', 'Premium', 'Pro']
        if tier_order.index(tier) < tier_order.index('Premium'):
            await ctx.send(embed=discord.Embed(
                title="Premium Required",
                description="Detailed stats require a **Premium** or **Pro** subscription.\nUse `t!subscribe` to upgrade.",
                color=config.COLORS['warning'],
            ))
            return

        async with aiosqlite.connect(config.DB_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            # Economy
            async with db_conn.execute("SELECT * FROM economy WHERE user_id = ?", (ctx.author.id,)) as cur:
                eco = await cur.fetchone()
            # Game stats
            async with db_conn.execute(
                "SELECT game, COUNT(*) as plays, SUM(score) as total_score, MAX(score) as best FROM game_scores WHERE user_id = ? GROUP BY game",
                (ctx.author.id,)
            ) as cur:
                game_rows = await cur.fetchall()
            # Fishing
            async with db_conn.execute(
                "SELECT total_caught, total_value, fishing_level, biggest_catch_type, biggest_catch_coins FROM fishing_stats WHERE user_id = ?",
                (ctx.author.id,)
            ) as cur:
                fish = await cur.fetchone()
            # Reminders count
            async with db_conn.execute(
                "SELECT COUNT(*) FROM reminders WHERE user_id = ?", (ctx.author.id,)
            ) as cur:
                reminder_count = (await cur.fetchone())[0]

        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Stats",
            color=config.COLORS['purple'],
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        if eco:
            embed.add_field(
                name="\U0001fa99 Economy",
                value=(
                    f"Coins: `{eco['coins']:,}`\n"
                    f"Gems: `{eco['gems'] or 0:,}`\n"
                    f"Tokens: `{eco['tokens'] or 0:,}`\n"
                    f"Total Earned: `{eco['total_earned']:,}`\n"
                    f"Streak: `{eco['daily_streak']}` days"
                ),
                inline=True,
            )

        if game_rows:
            game_lines = []
            for row in game_rows:
                game_lines.append(f"`{row['game']}` — {row['plays']}x played | best: `{row['best']:,}`")
            embed.add_field(name="\U0001f3ae Games", value="\n".join(game_lines), inline=False)

        if fish and fish['total_caught'] > 0:
            embed.add_field(
                name="\U0001f3a3 Fishing",
                value=(
                    f"Level: `{fish['fishing_level']}`\n"
                    f"Caught: `{fish['total_caught']:,}`\n"
                    f"Value Earned: `{fish['total_value']:,}` \U0001fa99\n"
                    + (f"Best Catch: `{fish['biggest_catch_type']}` (`{fish['biggest_catch_coins']:,}` \U0001fa99)" if fish['biggest_catch_type'] else "")
                ),
                inline=True,
            )

        embed.add_field(name="Reminders Set", value=f"`{reminder_count}`", inline=True)
        embed.set_footer(text=f"Tainment+ v{config.BOT_VERSION} | Premium Stats")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
