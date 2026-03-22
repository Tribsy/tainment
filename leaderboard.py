import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import config
import database as db
from server_settings import get_server_settings

GAME_LABELS = {
    'guess': 'Number Guessing',
    'trivia': 'Trivia',
    'hangman': 'Hangman',
    'wordle': 'Wordle',
}

MEDALS = [':first_place:', ':second_place:', ':third_place:']


async def _build_live_embed(guild: discord.Guild) -> discord.Embed:
    """Build the combined live leaderboard embed for a guild."""
    embed = discord.Embed(
        title=f"\U0001f3c6 {guild.name} — Live Leaderboards",
        color=config.COLORS['gold'],
    )
    embed.set_footer(text=f"Auto-updated every 10 minutes  |  Last updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}")

    # Top 5 Coins
    import aiosqlite
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT e.user_id, e.coins, u.username FROM economy e JOIN users u ON e.user_id = u.user_id ORDER BY e.coins DESC LIMIT 5"
        ) as cur:
            coin_rows = await cur.fetchall()

    coin_lines = []
    for i, row in enumerate(coin_rows):
        medal = MEDALS[i] if i < 3 else f"`{i+1}.`"
        member = guild.get_member(row['user_id'])
        name = member.display_name if member else row['username']
        coin_lines.append(f"{medal} **{name}** — `{row['coins']:,}` \U0001fa99")

    if coin_lines:
        embed.add_field(name="\U0001fa99 Richest Members", value="\n".join(coin_lines), inline=False)

    # Top 5 XP
    xp_rows = await db.get_level_leaderboard(guild.id, limit=5)
    xp_lines = []
    for i, row in enumerate(xp_rows):
        medal = MEDALS[i] if i < 3 else f"`{i+1}.`"
        member = guild.get_member(row['user_id'])
        name = member.display_name if member else f"User {row['user_id']}"
        xp_lines.append(f"{medal} **{name}** — Lvl `{row['level']}` | `{row['xp']:,}` XP")

    if xp_lines:
        embed.add_field(name="\u2b50 Top XP", value="\n".join(xp_lines), inline=False)

    # Top 5 Fishers
    fish_rows = await db.get_fishing_leaderboard(limit=5)
    fish_lines = []
    for i, row in enumerate(fish_rows):
        medal = MEDALS[i] if i < 3 else f"`{i+1}.`"
        member = guild.get_member(row['user_id'])
        name = member.display_name if member else (row['username'] or f"User {row['user_id']}")
        fish_lines.append(f"{medal} **{name}** — `{row['total_caught']:,}` caught · `{row['total_value']:,}` \U0001fa99")

    if fish_lines:
        embed.add_field(name="\U0001f3a3 Top Fishers", value="\n".join(fish_lines), inline=False)
    else:
        embed.add_field(name="\U0001f3a3 Top Fishers", value="*No fishing data yet — use `t!fish`!*", inline=False)

    return embed


class Leaderboard(commands.Cog, name="Leaderboard"):
    """Game score leaderboards + auto-updating live leaderboard channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.live_leaderboard_task.start()

    def cog_unload(self):
        self.live_leaderboard_task.cancel()

    @tasks.loop(minutes=10)
    async def live_leaderboard_task(self):
        """Post or edit the live leaderboard message in each guild's leaderboard channel."""
        for guild in self.bot.guilds:
            # Use configured channel first, fall back to name match
            lb_channel = None
            settings = await get_server_settings(guild.id)
            if settings and settings['leaderboard_channel']:
                lb_channel = guild.get_channel(settings['leaderboard_channel'])
            if not lb_channel:
                # Legacy fallback: find a channel with 'leaderboard' in name
                for ch in guild.text_channels:
                    if 'leaderboard' in ch.name.lower():
                        lb_channel = ch
                        break
            if not lb_channel:
                continue

            if not lb_channel.permissions_for(guild.me).send_messages:
                continue

            try:
                embed = await _build_live_embed(guild)
            except Exception:
                continue

            # Try to edit existing message
            stored = await db.get_bot_message(guild.id, 'live_leaderboard')
            if stored:
                try:
                    msg = await lb_channel.fetch_message(stored['message_id'])
                    await msg.edit(embed=embed)
                    continue
                except (discord.NotFound, discord.HTTPException):
                    pass  # Message deleted — post a new one

            # Post new message and store the ID
            try:
                msg = await lb_channel.send(embed=embed)
                await db.upsert_bot_message(guild.id, 'live_leaderboard', lb_channel.id, msg.id)
            except discord.HTTPException:
                pass

    @live_leaderboard_task.before_loop
    async def before_live_leaderboard(self):
        await self.bot.wait_until_ready()

    # ── Manual leaderboard command ─────────────────────────────────────────────

    @commands.command(name='leaderboard', aliases=['lb'], description='View game score leaderboards')
    async def leaderboard(self, ctx: commands.Context, game: str = None):
        if not game:
            embed = discord.Embed(
                title="Game Leaderboards",
                description="\n".join(f"`{k}` — {v}" for k, v in GAME_LABELS.items()),
                color=config.COLORS['primary'],
            )
            embed.set_footer(text="Use t!leaderboard <game> to view a specific board")
            await ctx.send(embed=embed)
            return

        game = game.lower()
        if game not in GAME_LABELS:
            keys = ', '.join(f'`{k}`' for k in GAME_LABELS)
            await ctx.send(embed=discord.Embed(
                description=f"Unknown game. Choose from: {keys}",
                color=config.COLORS['error'],
            ))
            return

        rows = await db.get_game_leaderboard(game, limit=10)
        if not rows:
            await ctx.send(embed=discord.Embed(
                description=f"No scores recorded for **{GAME_LABELS[game]}** yet.",
                color=config.COLORS['warning'],
            ))
            return

        lines = []
        for i, row in enumerate(rows):
            medal = MEDALS[i] if i < 3 else f"`{i+1}.`"
            try:
                member = ctx.guild.get_member(row['user_id']) if ctx.guild else None
                name = member.display_name if member else row['username'] or f"User {row['user_id']}"
            except Exception:
                name = row['username'] or f"User {row['user_id']}"
            lines.append(f"{medal} **{name}** — `{row['score']:,}`")

        embed = discord.Embed(
            title=f"{GAME_LABELS[game]} Leaderboard",
            description="\n".join(lines),
            color=config.COLORS['gold'],
        )
        embed.set_footer(text="Tainment+ Games")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))
