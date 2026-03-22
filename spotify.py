"""
Spotify integration cog for Tainment bot.

Commands (prefix t! or slash):
  Public (Free):    song, spotifyreleases
  Account linking:  spotify connect/disconnect/status
  Vibe+:            nowplaying, recenttracks
  Premium+:         topartists, mytoptracks
  Pro:              spotifyprofile
"""

import asyncio
import logging
import time

import discord
from discord.ext import commands

import config
import database as db
import music_api as sp

logger = logging.getLogger('tainment.spotify')

TIER_ORDER = ['Basic', 'Vibe', 'Premium', 'Pro']


def _tier_gte(user_tier: str, required: str) -> bool:
    return TIER_ORDER.index(user_tier) >= TIER_ORDER.index(required)


def _locked_embed(required: str) -> discord.Embed:
    return discord.Embed(
        title='\U0001f512 Feature Locked',
        description=f'This command requires **{required}** tier or higher.\nUpgrade with `t!subscribe`.',
        color=config.COLORS['error'],
    )


def _not_linked_embed() -> discord.Embed:
    return discord.Embed(
        title='Spotify Not Linked',
        description='Link your Spotify account first with `t!spotify connect`.',
        color=config.COLORS['warning'],
    )


def _fmt_duration(ms: int) -> str:
    secs = ms // 1000
    return f'{secs // 60}:{secs % 60:02d}'


def _progress_bar(progress_ms: int, duration_ms: int, width: int = 20) -> str:
    pct = progress_ms / duration_ms if duration_ms else 0
    filled = int(pct * width)
    return '\u25b6 ' + '\u2588' * filled + '\u2591' * (width - filled)


class SpotifyCog(commands.Cog, name='Spotify'):
    """Real-time Spotify data — search, now playing, top tracks, and more."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.oauth_server = sp.OAuthServer()

    async def cog_load(self):
        await self.oauth_server.start()

    async def cog_unload(self):
        await self.oauth_server.stop()

    # ── t!song ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name='song', description='Search Spotify for a track (Free)')
    async def song(self, ctx: commands.Context, *, query: str):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await ctx.defer()

        track = await sp.search_track(query)
        if not track:
            await ctx.send(embed=discord.Embed(
                description=f'No results for **{discord.utils.escape_markdown(query)}**.',
                color=config.COLORS['warning'],
            ))
            return

        artists = ', '.join(track['artists'])
        duration = _fmt_duration(track['duration_ms'])

        embed = discord.Embed(
            title=track['name'],
            url=track['external_url'],
            description=f'by **{artists}**\nAlbum: {track["album"]}',
            color=0x1db954,
        )
        if track['album_art']:
            embed.set_thumbnail(url=track['album_art'])
        embed.add_field(name='Duration', value=duration, inline=True)
        embed.add_field(name='Popularity', value=f'{track["popularity"]}/100', inline=True)
        if track.get('preview_url'):
            embed.add_field(name='Preview', value=f'[30s clip]({track["preview_url"]})', inline=True)
        embed.set_footer(text='Spotify')
        await ctx.send(embed=embed)

    # ── t!spotifyreleases ─────────────────────────────────────────────────────

    @commands.hybrid_command(name='spotifyreleases', description='New releases on Spotify this week (Free)')
    async def spotifyreleases(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        await ctx.defer()

        releases = await sp.get_new_releases(limit=8)
        if not releases:
            await ctx.send(embed=discord.Embed(
                description='No releases found. Check back later.',
                color=config.COLORS['warning'],
            ))
            return

        embed = discord.Embed(title='\U0001f195 New on Spotify', color=0x1db954)
        if releases[0]['album_art']:
            embed.set_thumbnail(url=releases[0]['album_art'])

        for r in releases[:6]:
            artists = ', '.join(r['artists'])
            label = 'Single' if r['type'] == 'single' else 'Album'
            embed.add_field(
                name=r['name'],
                value=f'{artists}\n`{label}` \u00b7 {r["release_date"]}\n[Open on Spotify]({r["external_url"]})',
                inline=True,
            )
        embed.set_footer(text='Spotify \u00b7 Updated every hour')
        await ctx.send(embed=embed)

    # ── t!spotify (group) ─────────────────────────────────────────────────────

    @commands.group(name='spotify', invoke_without_command=True)
    async def spotify_group(self, ctx: commands.Context):
        embed = discord.Embed(
            title='\U0001f4fb Spotify Commands',
            description=(
                '`t!spotify connect` \u2014 Link your Spotify account\n'
                '`t!spotify disconnect` \u2014 Unlink your account\n'
                '`t!spotify status` \u2014 Check your link status\n\n'
                '`t!nowplaying` \u2014 What you\'re listening to *(Vibe+)*\n'
                '`t!recenttracks` \u2014 Last 10 plays *(Vibe+)*\n'
                '`t!topartists [week|month|all]` \u2014 Top artists *(Premium+)*\n'
                '`t!mytoptracks [week|month|all]` \u2014 Top tracks *(Premium+)*\n'
                '`t!spotifyprofile` \u2014 Full music card *(Pro)*'
            ),
            color=0x1db954,
        )
        await ctx.send(embed=embed)

    @spotify_group.command(name='connect', description='Link your Spotify account to Tainment+')
    async def spotify_connect(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)

        if not config.SPOTIFY_CLIENT_ID:
            await ctx.send(embed=discord.Embed(
                description='Spotify integration is not configured on this bot.',
                color=config.COLORS['error'],
            ))
            return

        existing = await db.get_spotify_account(ctx.author.id)
        if existing:
            await ctx.send(embed=discord.Embed(
                title='Already Linked',
                description='Your Spotify account is already linked.\nUse `t!spotify disconnect` first to re-link.',
                color=config.COLORS['warning'],
            ))
            return

        url, state = sp.build_auth_url(ctx.author.id)

        try:
            dm_embed = discord.Embed(
                title='\U0001f4fb Link Your Spotify Account',
                description=(
                    f'Click below to authorize Tainment+ on Spotify.\n\n'
                    f'**[\U0001f517 Authorize Spotify]({url})**\n\n'
                    f'This link expires in **2 minutes**.'
                ),
                color=0x1db954,
            )
            dm_embed.set_footer(text='You will be redirected back automatically after approving.')
            await ctx.author.send(embed=dm_embed)
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                description='I couldn\'t DM you. Please enable DMs from server members and try again.',
                color=config.COLORS['error'],
            ))
            sp._pending_states.pop(state, None)
            return

        await ctx.send(embed=discord.Embed(
            description='\U0001f4e8 Check your DMs \u2014 authorization link sent! You have 2 minutes.',
            color=0x1db954,
        ))

        token_data = await sp.wait_for_auth(state, timeout=120.0)

        if not token_data:
            await ctx.send(embed=discord.Embed(
                title='Timed Out',
                description='Authorization timed out. Run `t!spotify connect` again when ready.',
                color=config.COLORS['error'],
            ))
            return

        expires_at = int(time.time()) + token_data.get('expires_in', 3600)
        await db.save_spotify_account(
            ctx.author.id,
            token_data['access_token'],
            token_data['refresh_token'],
            expires_at,
            token_data.get('scope', config.SPOTIFY_SCOPES),
        )

        profile = await sp.get_user_profile(ctx.author.id)
        name = profile['display_name'] if profile else 'your Spotify account'

        await ctx.send(embed=discord.Embed(
            title='\u2705 Spotify Linked!',
            description=f'Connected as **{name}**.\nTry `t!nowplaying`, `t!topartists`, and more!',
            color=config.COLORS['success'],
        ))

    @spotify_group.command(name='disconnect', description='Unlink your Spotify account')
    async def spotify_disconnect(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        if not await db.get_spotify_account(ctx.author.id):
            await ctx.send(embed=discord.Embed(
                description='No Spotify account is currently linked.',
                color=config.COLORS['warning'],
            ))
            return
        await db.delete_spotify_account(ctx.author.id)
        await ctx.send(embed=discord.Embed(
            title='Spotify Unlinked',
            description='Your Spotify account has been disconnected and your tokens deleted.',
            color=config.COLORS['success'],
        ))

    @spotify_group.command(name='status', description='Check your Spotify link status')
    async def spotify_status(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        account = await db.get_spotify_account(ctx.author.id)
        if not account:
            embed = discord.Embed(
                title='Not Linked',
                description='No Spotify account linked.\nUse `t!spotify connect` to get started.',
                color=config.COLORS['warning'],
            )
        else:
            profile = await sp.get_user_profile(ctx.author.id)
            name = profile['display_name'] if profile else 'Unknown'
            embed = discord.Embed(
                title='\u2705 Spotify Linked',
                description=f'Connected as **{name}**',
                color=config.COLORS['success'],
            )
        await ctx.send(embed=embed)

    # ── t!nowplaying ──────────────────────────────────────────────────────────

    @commands.hybrid_command(name='nowplaying', description='What you\'re listening to on Spotify right now (Vibe+)')
    async def nowplaying(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Vibe'):
            await ctx.send(embed=_locked_embed('Vibe'))
            return
        if not await db.get_spotify_account(ctx.author.id):
            await ctx.send(embed=_not_linked_embed())
            return

        await ctx.defer()
        data = await sp.get_nowplaying(ctx.author.id)

        if data is None:
            await ctx.send(embed=discord.Embed(
                description='Could not retrieve playback. Check your link with `t!spotify status`.',
                color=config.COLORS['warning'],
            ))
            return

        if not data.get('is_playing'):
            await ctx.send(embed=discord.Embed(
                title='\U0001f507 Nothing Playing',
                description='You\'re not playing anything on Spotify right now.',
                color=0x1db954,
            ))
            return

        artists = ', '.join(data['artists'])
        progress = _fmt_duration(data['progress_ms'])
        duration = _fmt_duration(data['duration_ms'])
        bar = _progress_bar(data['progress_ms'], data['duration_ms'])

        embed = discord.Embed(
            title=data['name'],
            url=data['external_url'],
            description=f'by **{artists}**\n\n{bar} {progress} / {duration}',
            color=0x1db954,
        )
        embed.set_author(
            name=f'{ctx.author.display_name} is listening to',
            icon_url=ctx.author.display_avatar.url,
        )
        if data.get('album_art'):
            embed.set_thumbnail(url=data['album_art'])
        embed.set_footer(text=f'Album: {data["album"]}  \u00b7  Spotify')
        await ctx.send(embed=embed)

    # ── t!recenttracks ────────────────────────────────────────────────────────

    @commands.hybrid_command(name='recenttracks', description='Your recently played Spotify tracks (Vibe+)')
    async def recenttracks(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Vibe'):
            await ctx.send(embed=_locked_embed('Vibe'))
            return
        if not await db.get_spotify_account(ctx.author.id):
            await ctx.send(embed=_not_linked_embed())
            return

        await ctx.defer()
        tracks = await sp.get_recent_tracks(ctx.author.id, limit=10)

        if not tracks:
            await ctx.send(embed=discord.Embed(
                description='No recent tracks found. Play something on Spotify first!',
                color=config.COLORS['warning'],
            ))
            return

        embed = discord.Embed(
            title=f'\U0001f3b5 {ctx.author.display_name}\'s Recent Tracks',
            color=0x1db954,
        )
        if tracks[0].get('album_art'):
            embed.set_thumbnail(url=tracks[0]['album_art'])

        lines = [
            f'`{i:2}.` [{t["name"]}]({t["external_url"]}) \u2014 {", ".join(t["artists"])}'
            for i, t in enumerate(tracks, 1)
        ]
        embed.description = '\n'.join(lines)
        embed.set_footer(text='Spotify \u00b7 Last 10 plays')
        await ctx.send(embed=embed)

    # ── t!topartists ──────────────────────────────────────────────────────────

    @commands.hybrid_command(name='topartists', description='Your top Spotify artists (Premium+)')
    async def topartists(self, ctx: commands.Context, time_range: str = 'month'):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Premium'):
            await ctx.send(embed=_locked_embed('Premium'))
            return
        if not await db.get_spotify_account(ctx.author.id):
            await ctx.send(embed=_not_linked_embed())
            return
        if time_range not in ('week', 'month', 'all'):
            time_range = 'month'

        await ctx.defer()
        artists = await sp.get_top_artists(ctx.author.id, time_range=time_range, limit=5)

        if not artists:
            await ctx.send(embed=discord.Embed(
                description='No data yet. Listen to more music on Spotify!',
                color=config.COLORS['warning'],
            ))
            return

        period = {'week': 'Last 4 Weeks', 'month': 'Last 6 Months', 'all': 'All Time'}[time_range]
        embed = discord.Embed(
            title=f'\U0001f3a4 {ctx.author.display_name}\'s Top Artists',
            description=f'Period: **{period}**',
            color=0x1db954,
        )
        medals = ['\U0001f947', '\U0001f948', '\U0001f949', '4\ufe0f\u20e3', '5\ufe0f\u20e3']
        for i, a in enumerate(artists):
            genres = ', '.join(a['genres']) if a['genres'] else 'No genres listed'
            embed.add_field(
                name=f'{medals[i]} {a["name"]}',
                value=f'Genres: {genres}\nFollowers: {a["followers"]:,}\n[Open]({a["external_url"]})',
                inline=True,
            )
        if artists[0].get('image'):
            embed.set_thumbnail(url=artists[0]['image'])
        embed.set_footer(text='Spotify \u00b7 Premium+ feature')
        await ctx.send(embed=embed)

    # ── t!mytoptracks ─────────────────────────────────────────────────────────

    @commands.hybrid_command(name='mytoptracks', description='Your top Spotify tracks (Premium+)')
    async def mytoptracks(self, ctx: commands.Context, time_range: str = 'month'):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Premium'):
            await ctx.send(embed=_locked_embed('Premium'))
            return
        if not await db.get_spotify_account(ctx.author.id):
            await ctx.send(embed=_not_linked_embed())
            return
        if time_range not in ('week', 'month', 'all'):
            time_range = 'month'

        await ctx.defer()
        tracks = await sp.get_top_tracks(ctx.author.id, time_range=time_range, limit=5)

        if not tracks:
            await ctx.send(embed=discord.Embed(
                description='No data yet. Listen to more music on Spotify!',
                color=config.COLORS['warning'],
            ))
            return

        period = {'week': 'Last 4 Weeks', 'month': 'Last 6 Months', 'all': 'All Time'}[time_range]
        embed = discord.Embed(
            title=f'\U0001f3b5 {ctx.author.display_name}\'s Top Tracks',
            description=f'Period: **{period}**',
            color=0x1db954,
        )
        medals = ['\U0001f947', '\U0001f948', '\U0001f949', '4\ufe0f\u20e3', '5\ufe0f\u20e3']
        for i, t in enumerate(tracks):
            artists = ', '.join(t['artists'])
            embed.add_field(
                name=f'{medals[i]} {t["name"]}',
                value=f'by {artists}\n[Open on Spotify]({t["external_url"]})',
                inline=True,
            )
        if tracks[0].get('album_art'):
            embed.set_thumbnail(url=tracks[0]['album_art'])
        embed.set_footer(text='Spotify \u00b7 Premium+ feature')
        await ctx.send(embed=embed)

    # ── t!spotifyprofile ──────────────────────────────────────────────────────

    @commands.hybrid_command(name='spotifyprofile', description='Your full Spotify music card (Pro)')
    async def spotifyprofile(self, ctx: commands.Context):
        await db.ensure_user(ctx.author.id, ctx.author.name)
        tier = await db.get_tier(ctx.author.id)
        if not _tier_gte(tier, 'Pro'):
            await ctx.send(embed=_locked_embed('Pro'))
            return
        if not await db.get_spotify_account(ctx.author.id):
            await ctx.send(embed=_not_linked_embed())
            return

        await ctx.defer()

        profile, top_artists, top_tracks, now = await asyncio.gather(
            sp.get_user_profile(ctx.author.id),
            sp.get_top_artists(ctx.author.id, time_range='month', limit=3),
            sp.get_top_tracks(ctx.author.id, time_range='month', limit=3),
            sp.get_nowplaying(ctx.author.id),
        )

        display = profile['display_name'] if profile else ctx.author.display_name
        embed = discord.Embed(title=f'\U0001f3b6 Spotify Profile \u2014 {display}', color=0x1db954)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

        if profile and profile.get('image'):
            embed.set_thumbnail(url=profile['image'])

        if now and now.get('is_playing'):
            artists = ', '.join(now['artists'])
            embed.add_field(
                name='\U0001f3a7 Now Playing',
                value=f'[{now["name"]}]({now["external_url"]}) \u2014 {artists}',
                inline=False,
            )

        if top_artists:
            embed.add_field(
                name='\U0001f3a4 Top Artists',
                value='\n'.join(f'`{i+1}.` {a["name"]}' for i, a in enumerate(top_artists)),
                inline=True,
            )

        if top_tracks:
            embed.add_field(
                name='\U0001f3b5 Top Tracks',
                value='\n'.join(f'`{i+1}.` {t["name"]}' for i, t in enumerate(top_tracks)),
                inline=True,
            )

        if profile:
            embed.add_field(
                name='\U0001f4ca Stats',
                value=f'Followers: {profile["followers"]:,}\n[Open Profile]({profile["external_url"]})',
                inline=True,
            )

        embed.set_footer(text='Spotify \u00b7 Pro feature \u00b7 Last 6 months')
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SpotifyCog(bot))
