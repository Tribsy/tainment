"""
Music Discovery cog.
Commands: recommend, hotsongs, genresearch, moodsearch, artistinfo, toptracks, newreleases
"""

import discord
from discord.ext import commands
import random
import aiosqlite
import config
import database as db
import music_data as md


TIER_ORDER = ['Basic', 'Vibe', 'Premium', 'Pro']


def _tier_gte(user_tier: str, required: str) -> bool:
    return TIER_ORDER.index(user_tier) >= TIER_ORDER.index(required)


def _locked_embed(required: str) -> discord.Embed:
    return discord.Embed(
        title="\U0001f512 Feature Locked",
        description=f"This command requires **{required}** tier or higher.\nUpgrade with `t!subscribe`.",
        color=config.COLORS['error'],
    )


def _song_embed(songs: list[dict], title: str, color: int, footer: str = '') -> discord.Embed:
    embed = discord.Embed(title=title, color=color)
    for s in songs:
        embed.add_field(
            name=f"\U0001f3b5 {s['title']} — {s['artist']}",
            value=s['description'],
            inline=False,
        )
    if footer:
        embed.set_footer(text=footer)
    return embed


class MusicDiscovery(commands.Cog, name="Music Discovery"):
    """Music discovery and recommendation commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── recommend ─────────────────────────────────────────────────────────────

    @commands.command(name='recommend', description='Get song recommendations (optionally by genre)')
    async def recommend(self, ctx: commands.Context, genre: str = None):
        await db.ensure_user(ctx.author.id, ctx.author.name)

        if genre and genre.lower() in md.SONG_RECOMMENDATIONS:
            pool = md.SONG_RECOMMENDATIONS[genre.lower()]
        else:
            all_songs = [s for songs in md.SONG_RECOMMENDATIONS.values() for s in songs]
            pool = all_songs

        picks = random.sample(pool, min(3, len(pool)))
        genre_str = genre.capitalize() if genre else 'Mixed'
        embed = _song_embed(
            picks,
            f"\U0001f3b6 Recommended for You ({genre_str})",
            config.COLORS['primary'],
            f"Try t!genresearch <genre> for more  |  Genres: {', '.join(md.GENRE_LIST)}",
        )
        await ctx.send(embed=embed)

    # ── hotsongs ──────────────────────────────────────────────────────────────

    @commands.command(name='hotsongs', aliases=['hot', 'trending'], description="This server's hottest tracks this week")
    @commands.guild_only()
    async def hotsongs(self, ctx: commands.Context):
        async with aiosqlite.connect(config.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT song, artist, COUNT(*) as shares
                FROM music_shared_tracks
                WHERE guild_id = ? AND shared_at >= datetime('now', '-7 days')
                GROUP BY song, artist
                ORDER BY shares DESC
                LIMIT 5
            """, (ctx.guild.id,)) as cur:
                rows = await cur.fetchall()

        embed = discord.Embed(
            title=f"\U0001f525 Hot Songs — {ctx.guild.name}",
            color=0xff6b35,
        )

        if not rows:
            embed.description = "No tracks shared this week yet!\nUse `t!sharetrack <song> - <artist>` to add to the chart."
        else:
            medals = ['\U0001f947', '\U0001f948', '\U0001f949', '4\ufe0f\u20e3', '5\ufe0f\u20e3']
            for i, row in enumerate(rows):
                embed.add_field(
                    name=f"{medals[i]} {row['song']} — {row['artist']}",
                    value=f"`{row['shares']}` share{'s' if row['shares'] != 1 else ''}",
                    inline=False,
                )

        embed.set_footer(text="Share tracks with t!sharetrack  |  Resets weekly")
        await ctx.send(embed=embed)

    # ── genresearch ───────────────────────────────────────────────────────────

    @commands.command(name='genresearch', aliases=['genre'], description='Get curated recommendations for a specific genre (Vibe+)')
    async def genresearch(self, ctx: commands.Context, genre: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Vibe'):
            await ctx.send(embed=_locked_embed('Vibe'))
            return

        genre = genre.lower()
        if genre not in md.SONG_RECOMMENDATIONS:
            embed = discord.Embed(
                description=f"Unknown genre. Available: `{'`, `'.join(md.SONG_RECOMMENDATIONS.keys())}`",
                color=config.COLORS['warning'],
            )
            await ctx.send(embed=embed)
            return

        pool = md.SONG_RECOMMENDATIONS[genre]
        picks = random.sample(pool, min(5, len(pool)))
        embed = _song_embed(
            picks,
            f"\U0001f3b5 {genre.capitalize()} Picks",
            config.COLORS['purple'],
            "Run again for different picks",
        )
        await ctx.send(embed=embed)

    # ── moodsearch ────────────────────────────────────────────────────────────

    @commands.command(name='moodsearch', aliases=['mood'], description='Get song recommendations by mood (Vibe+)')
    async def moodsearch(self, ctx: commands.Context, mood: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Vibe'):
            await ctx.send(embed=_locked_embed('Vibe'))
            return

        mood = mood.lower()
        if mood not in md.MOOD_SONGS:
            embed = discord.Embed(
                description=f"Unknown mood. Available: `{'`, `'.join(md.MOOD_LIST)}`",
                color=config.COLORS['warning'],
            )
            await ctx.send(embed=embed)
            return

        pool = md.MOOD_SONGS[mood]
        picks = random.sample(pool, min(4, len(pool)))
        mood_colors = {
            'hype': 0xff4500, 'chill': 0x00bcd4, 'sad': 0x5c6bc0,
            'focus': 0x4caf50, 'party': 0xe040fb, 'workout': 0xf44336,
        }
        embed = _song_embed(
            picks,
            f"\U0001f3b6 {mood.capitalize()} Vibes",
            mood_colors.get(mood, config.COLORS['primary']),
            f"Mood: {mood}  |  Run again for different picks",
        )
        await ctx.send(embed=embed)

    # ── artistinfo ────────────────────────────────────────────────────────────

    @commands.command(name='artistinfo', aliases=['artist'], description='View an artist profile card (Premium+)')
    async def artistinfo(self, ctx: commands.Context, *, artist: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Premium'):
            await ctx.send(embed=_locked_embed('Premium'))
            return

        # Case-insensitive lookup
        key = next((k for k in md.ARTIST_INFO if k.lower() == artist.lower()), None)
        if not key:
            await ctx.send(embed=discord.Embed(
                description=f"Artist `{artist}` not found. Available artists: `{'`, `'.join(md.ARTIST_INFO.keys())}`",
                color=config.COLORS['warning'],
            ))
            return

        info = md.ARTIST_INFO[key]
        embed = discord.Embed(
            title=f"\U0001f3a4 {key}",
            description=info['fun_fact'],
            color=config.COLORS['gold'],
        )
        embed.add_field(name="Genre", value=info['genre'], inline=True)
        embed.add_field(name="Known For", value=info['known_for'], inline=False)
        embed.add_field(
            name="Top Songs",
            value='\n'.join(f"\U0001f3b5 {s}" for s in info['top_songs']),
            inline=False,
        )
        embed.set_footer(text="t!recommend to find similar artists")
        await ctx.send(embed=embed)

    # ── toptracks ─────────────────────────────────────────────────────────────

    @commands.command(name='toptracks', description='Most shared songs across all servers (Premium+)')
    async def toptracks(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Premium'):
            await ctx.send(embed=_locked_embed('Premium'))
            return

        async with aiosqlite.connect(config.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT song, artist, COUNT(*) as shares
                FROM music_shared_tracks
                WHERE shared_at >= datetime('now', '-30 days')
                GROUP BY song, artist
                ORDER BY shares DESC
                LIMIT 10
            """) as cur:
                rows = await cur.fetchall()

        embed = discord.Embed(
            title="\U0001f30d Global Top Tracks (Last 30 Days)",
            color=config.COLORS['gold'],
        )

        if not rows:
            embed.description = "No tracks have been shared globally yet. Be the first with `t!sharetrack`!"
        else:
            medals = ['\U0001f947', '\U0001f948', '\U0001f949']
            for i, row in enumerate(rows):
                prefix = medals[i] if i < 3 else f"`{i+1}.`"
                embed.add_field(
                    name=f"{prefix} {row['song']} — {row['artist']}",
                    value=f"`{row['shares']}` global shares",
                    inline=False,
                )

        embed.set_footer(text="Aggregated across all Tainment+ servers")
        await ctx.send(embed=embed)

    # ── newreleases ───────────────────────────────────────────────────────────

    @commands.command(name='newreleases', aliases=['new', 'fresh'], description='Curated new releases this week (Pro)')
    async def newreleases(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Pro'):
            await ctx.send(embed=_locked_embed('Pro'))
            return

        embed = _song_embed(
            md.NEW_RELEASES,
            "\U0001f195 New Releases",
            config.COLORS['info'],
            "Curated weekly by the Tainment+ team",
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicDiscovery(bot))
