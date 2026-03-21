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
    'Vibe': ' [VIBE]',
    'Premium': ' [PREMIUM]',
    'Pro': ' [PRO]',
}


class Profile(commands.Cog, name="Profile"):
    """User profile cards with stats."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name='profile', aliases=['me', 'card'], description='View your profile card')
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

        color = TIER_COLORS.get(tier, config.COLORS['primary'])
        badge = TIER_BADGES.get(tier, '')
        vip_badge = ' [VIP]' if has_vip else ''

        embed = discord.Embed(
            title=f"{target.display_name}{badge}{vip_badge}",
            color=color,
        )
        embed.set_thumbnail(url=target.display_avatar.url)

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

        embed.add_field(name="Coins", value=f"`{coins:,}`", inline=True)
        embed.add_field(name="Total Earned", value=f"`{total_earned:,}`", inline=True)
        embed.add_field(name="Daily Streak", value=f"`{streak}` days", inline=True)

        embed.add_field(name="Tier", value=f"**{tier}**", inline=True)
        embed.add_field(name="Games Played", value=f"`{games_played}`", inline=True)
        embed.add_field(name="Total Score", value=f"`{total_score:,}`", inline=True)

        if active_items:
            item_names = []
            for key in active_items:
                item_data = config.SHOP_ITEMS.get(key)
                if item_data:
                    item_names.append(item_data['name'])
            if item_names:
                embed.add_field(name="Active Items", value=', '.join(item_names), inline=False)

        # Member since
        if hasattr(target, 'joined_at') and target.joined_at:
            ts = int(target.joined_at.timestamp())
            embed.add_field(name="Joined Server", value=f"<t:{ts}:R>", inline=True)

        embed.set_footer(text=f"Tainment+ v{config.BOT_VERSION}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='serverinfo', description='View server information')
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

    @commands.hybrid_command(name='userinfo', description='View info about a user')
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

    @commands.hybrid_command(name='avatar', aliases=['av', 'pfp'], description="View a user's avatar")
    async def avatar(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        embed = discord.Embed(
            title=f"{target.display_name}'s Avatar",
            color=config.COLORS['primary'],
        )
        embed.set_image(url=target.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
