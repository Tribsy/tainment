"""
Music Profiles cog.
Commands: musicprofile, setgenre, setartist, sharetrack, musicwrapped, playlist (group)
"""

import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime, timezone, timedelta
import config
import database as db
import music_data as md


TIER_ORDER = ['Basic', 'Vibe', 'Premium', 'Pro']
MAX_ARTISTS = {'Basic': 5, 'Vibe': 10, 'Premium': 15, 'Pro': 999}
MAX_PLAYLISTS = {'Basic': 0, 'Vibe': 3, 'Premium': 5, 'Pro': 999}


def _tier_gte(user_tier: str, required: str) -> bool:
    return TIER_ORDER.index(user_tier) >= TIER_ORDER.index(required)


def _locked_embed(required: str) -> discord.Embed:
    return discord.Embed(
        title="\U0001f512 Feature Locked",
        description=f"This command requires **{required}** tier or higher.\nUpgrade with `t!subscribe`.",
        color=config.COLORS['error'],
    )


async def _ensure_music_profile(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO music_profiles (user_id) VALUES (?)", (user_id,)
        )
        await conn.commit()


async def _get_music_profile(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM music_profiles WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchone()


async def _update_streak(user_id: int):
    """Increment music activity streak if last activity was within 48h, else reset."""
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT listening_streak, last_music_activity FROM music_profiles WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return

        now = datetime.now(timezone.utc)
        last = row['last_music_activity']
        streak = row['listening_streak'] or 0

        if last:
            try:
                last_dt = datetime.fromisoformat(last.replace('Z', '+00:00'))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                diff = now - last_dt
                if diff < timedelta(hours=48):
                    streak += 1
                else:
                    streak = 1
            except Exception:
                streak = 1
        else:
            streak = 1

        await conn.execute("""
            UPDATE music_profiles
            SET listening_streak = ?, last_music_activity = datetime('now'),
                total_activities = total_activities + 1
            WHERE user_id = ?
        """, (streak, user_id))
        await conn.commit()


class MusicProfiles(commands.Cog, name="Music Profiles"):
    """Music taste profiles, sharing, and playlists."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── musicprofile ──────────────────────────────────────────────────────────

    @commands.command(name='musicprofile', aliases=['mprofile', 'mp'], description='View your music taste card')
    async def musicprofile(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author
        await db.ensure_user(target.id, target.name)
        await _ensure_music_profile(target.id)
        profile = await _get_music_profile(target.id)

        async with aiosqlite.connect(config.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT artist FROM music_favourite_artists WHERE user_id = ? ORDER BY added_at ASC LIMIT 5",
                (target.id,)
            ) as cur:
                artists = [r['artist'] for r in await cur.fetchall()]

        has_badge = await db.has_active_item(target.id, 'music_badge')
        has_crown = await db.has_active_item(target.id, 'dj_crown')

        badge_str = ''
        if has_badge:
            badge_str += ' \U0001f3b5 Music Fanatic'
        if has_crown:
            badge_str += ' \U0001f451 DJ Crown'

        embed = discord.Embed(
            title=f"\U0001f3b6 {target.display_name}'s Music Profile{badge_str}",
            color=0xe040fb,
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(
            name="\U0001f3b8 Favourite Genre",
            value=profile['favourite_genre'] or '*Not set* — use `t!setgenre`*',
            inline=True,
        )
        embed.add_field(
            name="\U0001f525 Listening Streak",
            value=f"`{profile['listening_streak'] or 0}` days",
            inline=True,
        )
        embed.add_field(
            name="\U0001f3af Total Activities",
            value=f"`{profile['total_activities'] or 0}`",
            inline=True,
        )
        embed.add_field(
            name="\U0001f3a4 Favourite Artists",
            value='\n'.join(f"\u2022 {a}" for a in artists) if artists else '*None set — use `t!setartist`*',
            inline=False,
        )
        embed.add_field(
            name="\U0001fa99 Music Earnings",
            value=(
                f"Coins: `{profile['total_music_coins'] or 0:,}` \U0001fa99  "
                f"Gems: `{profile['total_music_gems'] or 0:,}` \U0001f48e  "
                f"Tokens: `{profile['total_music_tokens'] or 0:,}` \U0001f3ab"
            ),
            inline=False,
        )
        embed.set_footer(text="Tainment+ Music System")
        await ctx.send(embed=embed)

    # ── setgenre ──────────────────────────────────────────────────────────────

    @commands.command(name='setgenre', description='Set your favourite music genre')
    async def setgenre(self, ctx: commands.Context, genre: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await _ensure_music_profile(ctx.author.id)

        genre = genre.lower()
        if genre not in md.GENRE_LIST:
            await ctx.send(embed=discord.Embed(
                description=f"Unknown genre. Options: `{'`, `'.join(md.GENRE_LIST)}`",
                color=config.COLORS['warning'],
            ))
            return

        async with aiosqlite.connect(config.DB_PATH) as conn:
            await conn.execute(
                "UPDATE music_profiles SET favourite_genre = ? WHERE user_id = ?",
                (genre, ctx.author.id)
            )
            await conn.commit()

        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Favourite genre set to **{genre.capitalize()}**.",
            color=config.COLORS['success'],
        ))

    # ── setartist ─────────────────────────────────────────────────────────────

    @commands.command(name='setartist', description='Add an artist to your favourites')
    async def setartist(self, ctx: commands.Context, *, artist: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await _ensure_music_profile(ctx.author.id)
        tier = await db.get_tier(ctx.author.id)

        max_artists = MAX_ARTISTS.get(tier, 5)

        async with aiosqlite.connect(config.DB_PATH) as conn:
            async with conn.execute(
                "SELECT COUNT(*) FROM music_favourite_artists WHERE user_id = ?", (ctx.author.id,)
            ) as cur:
                count = (await cur.fetchone())[0]

            if count >= max_artists:
                await ctx.send(embed=discord.Embed(
                    description=(
                        f"You've reached your artist limit (`{count}/{max_artists}`).\n"
                        f"Upgrade your tier for more slots, or wait — Pro tier has unlimited slots."
                    ),
                    color=config.COLORS['warning'],
                ))
                return

            # Check duplicate
            async with conn.execute(
                "SELECT id FROM music_favourite_artists WHERE user_id = ? AND LOWER(artist) = LOWER(?)",
                (ctx.author.id, artist)
            ) as cur:
                if await cur.fetchone():
                    await ctx.send(embed=discord.Embed(
                        description=f"**{artist}** is already in your favourites.",
                        color=config.COLORS['warning'],
                    ))
                    return

            await conn.execute(
                "INSERT INTO music_favourite_artists (user_id, artist) VALUES (?, ?)",
                (ctx.author.id, artist)
            )
            await conn.commit()

        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Added **{artist}** to your favourite artists. (`{count+1}/{max_artists}`)",
            color=config.COLORS['success'],
        ))

    # ── sharetrack ────────────────────────────────────────────────────────────

    @commands.command(name='sharetrack', aliases=['share', 'st'], description='Share a song with the server (daily reward)')
    @commands.guild_only()
    @commands.cooldown(1, 21600, commands.BucketType.user)
    async def sharetrack(self, ctx: commands.Context, *, track: str):
        """Usage: t!sharetrack Song Title - Artist Name"""
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await _ensure_music_profile(ctx.author.id)

        if ' - ' not in track:
            await ctx.send(embed=discord.Embed(
                description="Format: `t!sharetrack Song Title - Artist Name`",
                color=config.COLORS['warning'],
            ))
            return

        parts = track.split(' - ', 1)
        song = parts[0].strip()
        artist = parts[1].strip()

        tier = await db.get_tier(ctx.author.id)
        coins_reward = {'Basic': 25, 'Vibe': 30, 'Premium': 40, 'Pro': 60}.get(tier, 25)

        # hot_boost doubles share count
        qty = 2 if await db.has_active_item(ctx.author.id, 'hot_boost') else 1

        async with aiosqlite.connect(config.DB_PATH) as conn:
            for _ in range(qty):
                await conn.execute(
                    "INSERT INTO music_shared_tracks (user_id, guild_id, song, artist) VALUES (?, ?, ?, ?)",
                    (ctx.author.id, ctx.guild.id, song, artist)
                )
            await conn.commit()

        await db.earn_currency(ctx.author.id, 'coins', coins_reward)
        await _update_streak(ctx.author.id)

        # Update music profile earnings
        async with aiosqlite.connect(config.DB_PATH) as conn:
            await conn.execute(
                "UPDATE music_profiles SET total_music_coins = total_music_coins + ? WHERE user_id = ?",
                (coins_reward, ctx.author.id)
            )
            await conn.commit()

        boost_note = " *(Hot Boost active — counted double!)*" if qty == 2 else ""
        embed = discord.Embed(
            title="\U0001f3b5 Track Shared!",
            description=(
                f"**{song}** by **{artist}** added to the server chart!\n"
                f"+**{coins_reward}** \U0001fa99{boost_note}\n\n"
                f"Check the chart with `t!hotsongs`"
            ),
            color=0xe040fb,
        )
        embed.set_footer(text="Daily share — come back tomorrow for another reward")
        await ctx.send(embed=embed)

    # ── musicwrapped ──────────────────────────────────────────────────────────

    @commands.command(name='musicwrapped', aliases=['wrapped', 'mwrapped'], description='Your monthly music summary (Vibe+)')
    @commands.cooldown(1, 2592000, commands.BucketType.user)
    async def musicwrapped(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Vibe'):
            await ctx.send(embed=_locked_embed('Vibe'))
            return

        await _ensure_music_profile(ctx.author.id)
        profile = await _get_music_profile(ctx.author.id)

        async with aiosqlite.connect(config.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT artist FROM music_favourite_artists WHERE user_id = ? ORDER BY added_at ASC LIMIT 3",
                (ctx.author.id,)
            ) as cur:
                artists = [r['artist'] for r in await cur.fetchall()]

            async with conn.execute("""
                SELECT song, COUNT(*) as cnt
                FROM music_shared_tracks
                WHERE user_id = ? AND shared_at >= datetime('now', '-30 days')
                GROUP BY song ORDER BY cnt DESC LIMIT 3
            """, (ctx.author.id,)) as cur:
                top_shared = await cur.fetchall()

        embed = discord.Embed(
            title=f"\U0001f3b5 {ctx.author.display_name}'s Music Wrapped",
            description="Your last 30 days of music activity.",
            color=0xe040fb,
        )
        embed.add_field(name="\U0001f3b8 Favourite Genre", value=profile['favourite_genre'] or 'Not set', inline=True)
        embed.add_field(name="\U0001f525 Listening Streak", value=f"`{profile['listening_streak'] or 0}` days", inline=True)
        embed.add_field(name="\U0001f3af Activities", value=f"`{profile['total_activities'] or 0}` total", inline=True)
        embed.add_field(
            name="\U0001f3a4 Favourite Artists",
            value='\n'.join(f"\u2022 {a}" for a in artists) if artists else 'None',
            inline=False,
        )
        if top_shared:
            embed.add_field(
                name="\U0001f4e4 Most Shared This Month",
                value='\n'.join(f"\u2022 **{r['song']}** ({r['cnt']}x)" for r in top_shared),
                inline=False,
            )
        embed.add_field(
            name="\U0001fa99 Lifetime Music Earnings",
            value=(
                f"Coins: `{profile['total_music_coins'] or 0:,}` \U0001fa99  "
                f"Gems: `{profile['total_music_gems'] or 0:,}` \U0001f48e  "
                f"Tokens: `{profile['total_music_tokens'] or 0:,}` \U0001f3ab"
            ),
            inline=False,
        )
        embed.set_footer(text="Wrapped refreshes monthly  |  Use t!wrapped_token to unlock early")
        await ctx.send(embed=embed)

    # ── playlist group ────────────────────────────────────────────────────────

    @commands.group(name='playlist', aliases=['pl'], description='Manage your music playlists (Vibe+)')
    async def playlist(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=discord.Embed(
                description=(
                    "**Playlist commands:**\n"
                    "`t!playlist create <name>` — Create a playlist\n"
                    "`t!playlist add <name> <song> - <artist>` — Add a song\n"
                    "`t!playlist view <name> [@user]` — View a playlist\n"
                    "`t!playlist list` — List your playlists\n"
                    "`t!playlist delete <name>` — Delete a playlist"
                ),
                color=config.COLORS['primary'],
            ))

    @playlist.command(name='create', description='Create a new playlist')
    async def playlist_create(self, ctx: commands.Context, *, name: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Vibe'):
            await ctx.send(embed=_locked_embed('Vibe'))
            return

        max_pl = MAX_PLAYLISTS.get(tier, 3)
        # Check slot boost
        async with aiosqlite.connect(config.DB_PATH) as conn:
            async with conn.execute(
                "SELECT COUNT(*) FROM music_playlists WHERE owner_id = ?", (ctx.author.id,)
            ) as cur:
                count = (await cur.fetchone())[0]

        if count >= max_pl:
            await ctx.send(embed=discord.Embed(
                description=f"Playlist limit reached (`{count}/{max_pl}`). Upgrade tier or buy a **Playlist Slot** from the shop.",
                color=config.COLORS['warning'],
            ))
            return

        async with aiosqlite.connect(config.DB_PATH) as conn:
            async with conn.execute(
                "SELECT id FROM music_playlists WHERE owner_id = ? AND LOWER(name) = LOWER(?)",
                (ctx.author.id, name)
            ) as cur:
                if await cur.fetchone():
                    await ctx.send(embed=discord.Embed(
                        description=f"You already have a playlist named **{name}**.",
                        color=config.COLORS['warning'],
                    ))
                    return
            await conn.execute(
                "INSERT INTO music_playlists (owner_id, name) VALUES (?, ?)",
                (ctx.author.id, name)
            )
            await conn.commit()

        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Playlist **{name}** created! Add songs with `t!playlist add {name} <song> - <artist>`.",
            color=config.COLORS['success'],
        ))

    @playlist.command(name='add', description='Add a song to a playlist')
    async def playlist_add(self, ctx: commands.Context, playlist_name: str, *, track: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Vibe'):
            await ctx.send(embed=_locked_embed('Vibe'))
            return

        if ' - ' not in track:
            await ctx.send(embed=discord.Embed(
                description="Format: `t!playlist add <name> Song Title - Artist Name`",
                color=config.COLORS['warning'],
            ))
            return

        song, artist = [p.strip() for p in track.split(' - ', 1)]

        async with aiosqlite.connect(config.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT id, owner_id, collab_user FROM music_playlists WHERE LOWER(name) = LOWER(?) AND (owner_id = ? OR collab_user = ?)",
                (playlist_name, ctx.author.id, ctx.author.id)
            ) as cur:
                pl = await cur.fetchone()

            if not pl:
                await ctx.send(embed=discord.Embed(
                    description=f"Playlist **{playlist_name}** not found, or you don't have access.",
                    color=config.COLORS['error'],
                ))
                return

            async with conn.execute(
                "SELECT COUNT(*) FROM music_playlist_tracks WHERE playlist_id = ?", (pl['id'],)
            ) as cur:
                track_count = (await cur.fetchone())[0]

            await conn.execute(
                "INSERT INTO music_playlist_tracks (playlist_id, song, artist, added_by, position) VALUES (?, ?, ?, ?, ?)",
                (pl['id'], song, artist, ctx.author.id, track_count + 1)
            )
            await conn.commit()

        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Added **{song}** by **{artist}** to **{playlist_name}**.",
            color=config.COLORS['success'],
        ))

    @playlist.command(name='view', description='View a playlist')
    async def playlist_view(self, ctx: commands.Context, playlist_name: str, user: discord.Member = None):
        target = user or ctx.author

        async with aiosqlite.connect(config.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM music_playlists WHERE owner_id = ? AND LOWER(name) = LOWER(?)",
                (target.id, playlist_name)
            ) as cur:
                pl = await cur.fetchone()

            if not pl:
                await ctx.send(embed=discord.Embed(
                    description=f"Playlist **{playlist_name}** not found for {target.display_name}.",
                    color=config.COLORS['error'],
                ))
                return

            async with conn.execute(
                "SELECT song, artist, position FROM music_playlist_tracks WHERE playlist_id = ? ORDER BY position ASC LIMIT 20",
                (pl['id'],)
            ) as cur:
                tracks = await cur.fetchall()

        embed = discord.Embed(
            title=f"\U0001f3b5 {pl['name']} — {target.display_name}",
            color=config.COLORS['primary'],
        )
        if not tracks:
            embed.description = "This playlist is empty. Add songs with `t!playlist add`."
        else:
            embed.description = '\n'.join(
                f"`{t['position']}.` **{t['song']}** — {t['artist']}"
                for t in tracks
            )
        embed.set_footer(text=f"{len(tracks)} track{'s' if len(tracks) != 1 else ''}")
        await ctx.send(embed=embed)

    @playlist.command(name='list', description='List your playlists')
    async def playlist_list(self, ctx: commands.Context):
        async with aiosqlite.connect(config.DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT name, (SELECT COUNT(*) FROM music_playlist_tracks WHERE playlist_id=music_playlists.id) as tc FROM music_playlists WHERE owner_id = ? ORDER BY created_at DESC",
                (ctx.author.id,)
            ) as cur:
                playlists = await cur.fetchall()

        if not playlists:
            await ctx.send(embed=discord.Embed(
                description="You have no playlists. Create one with `t!playlist create <name>`.",
                color=config.COLORS['warning'],
            ))
            return

        tier = await db.get_tier(ctx.author.id)
        max_pl = MAX_PLAYLISTS.get(tier, 3)
        embed = discord.Embed(
            title=f"\U0001f3b5 {ctx.author.display_name}'s Playlists ({len(playlists)}/{max_pl})",
            color=config.COLORS['primary'],
        )
        for pl in playlists:
            embed.add_field(
                name=pl['name'],
                value=f"`{pl['tc']}` track{'s' if pl['tc'] != 1 else ''}",
                inline=True,
            )
        await ctx.send(embed=embed)

    @playlist.command(name='delete', description='Delete a playlist')
    async def playlist_delete(self, ctx: commands.Context, *, playlist_name: str):
        async with aiosqlite.connect(config.DB_PATH) as conn:
            async with conn.execute(
                "SELECT id FROM music_playlists WHERE owner_id = ? AND LOWER(name) = LOWER(?)",
                (ctx.author.id, playlist_name)
            ) as cur:
                pl = await cur.fetchone()

            if not pl:
                await ctx.send(embed=discord.Embed(
                    description=f"Playlist **{playlist_name}** not found.",
                    color=config.COLORS['error'],
                ))
                return

            await conn.execute("DELETE FROM music_playlist_tracks WHERE playlist_id = ?", (pl[0],))
            await conn.execute("DELETE FROM music_playlists WHERE id = ?", (pl[0],))
            await conn.commit()

        await ctx.send(embed=discord.Embed(
            description=f"\u2705 Playlist **{playlist_name}** deleted.",
            color=config.COLORS['success'],
        ))


async def _init_music_tables():
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_profiles (
                user_id INTEGER PRIMARY KEY,
                favourite_genre TEXT,
                listening_streak INTEGER DEFAULT 0,
                last_music_activity TIMESTAMP,
                total_activities INTEGER DEFAULT 0,
                total_music_coins INTEGER DEFAULT 0,
                total_music_gems INTEGER DEFAULT 0,
                total_music_tokens INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_favourite_artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                artist TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_shared_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                song TEXT,
                artist TEXT,
                shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                name TEXT,
                is_public INTEGER DEFAULT 1,
                collab_user INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_playlist_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER,
                song TEXT,
                artist TEXT,
                added_by INTEGER,
                position INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES music_playlists(id)
            )
        """)
        await conn.commit()


async def setup(bot: commands.Bot):
    await _init_music_tables()
    await bot.add_cog(MusicProfiles(bot))
