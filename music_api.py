"""
Spotify API client + OAuth callback server for Tainment bot.

Uses pure aiohttp for all HTTP calls — no extra Spotify SDK required.
Handles Client Credentials (public) and per-user Authorization Code tokens.
"""

import asyncio
import json
import logging
import secrets
import time
import urllib.parse

import aiohttp
from aiohttp import web

import config
import database as db

logger = logging.getLogger('tainment.spotify')

# ── In-memory OAuth state stores ─────────────────────────────────────────────
# state -> discord_user_id (waiting for callback)
_pending_states: dict[str, int] = {}
# state -> raw token dict from Spotify (callback completed)
_completed_tokens: dict[str, dict] = {}

# ── Client Credentials token cache ───────────────────────────────────────────
_app_token: str | None = None
_app_token_expiry: float = 0.0

_SPOTIFY_ACCOUNTS_URL = 'https://accounts.spotify.com/api/token'
_SPOTIFY_API_BASE = 'https://api.spotify.com/v1'
_TIME_RANGE_MAP = {'week': 'short_term', 'month': 'medium_term', 'all': 'long_term'}


# ── Token helpers ─────────────────────────────────────────────────────────────

async def _get_app_token() -> str:
    """Return a valid Client Credentials access token, refreshing as needed."""
    global _app_token, _app_token_expiry
    if _app_token and time.time() < _app_token_expiry - 60:
        return _app_token
    async with aiohttp.ClientSession() as session:
        async with session.post(
            _SPOTIFY_ACCOUNTS_URL,
            data={'grant_type': 'client_credentials'},
            auth=aiohttp.BasicAuth(config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        ) as resp:
            data = await resp.json()
    if 'access_token' not in data:
        raise RuntimeError(f'Client Credentials token request failed: {data}')
    _app_token = data['access_token']
    _app_token_expiry = time.time() + data.get('expires_in', 3600)
    logger.debug('Refreshed Spotify app token.')
    return _app_token


async def exchange_code(code: str) -> dict:
    """Exchange an authorization code for user tokens."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            _SPOTIFY_ACCOUNTS_URL,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': config.SPOTIFY_REDIRECT_URI,
            },
            auth=aiohttp.BasicAuth(config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        ) as resp:
            return await resp.json()


async def _refresh_user_token(refresh_token: str) -> dict:
    """Refresh a user's access token. Returns raw token dict."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            _SPOTIFY_ACCOUNTS_URL,
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
            },
            auth=aiohttp.BasicAuth(config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        ) as resp:
            return await resp.json()


async def _get_valid_user_token(user_id: int) -> str | None:
    """Return a valid access token for a Discord user, refreshing if needed. None if not linked."""
    account = await db.get_spotify_account(user_id)
    if not account:
        return None
    if time.time() > account['expires_at'] - 60:
        data = await _refresh_user_token(account['refresh_token'])
        if 'access_token' not in data:
            logger.warning(f'Token refresh failed for user {user_id}: {data}')
            return None
        new_expiry = int(time.time()) + data.get('expires_in', 3600)
        new_refresh = data.get('refresh_token', account['refresh_token'])
        await db.save_spotify_account(user_id, data['access_token'], new_refresh, new_expiry, account['scopes'])
        return data['access_token']
    return account['access_token']


# ── OAuth URL builder ─────────────────────────────────────────────────────────

def build_auth_url(discord_user_id: int) -> tuple[str, str]:
    """Build a Spotify authorization URL. Returns (url, state)."""
    state = secrets.token_urlsafe(16)
    _pending_states[state] = discord_user_id
    params = {
        'client_id': config.SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': config.SPOTIFY_REDIRECT_URI,
        'scope': config.SPOTIFY_SCOPES,
        'state': state,
    }
    url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode(params)
    return url, state


async def wait_for_auth(state: str, timeout: float = 120.0) -> dict | None:
    """Poll until the OAuth callback completes. Returns token dict or None on timeout/error."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if state in _completed_tokens:
            return _completed_tokens.pop(state)
        await asyncio.sleep(2)
    _pending_states.pop(state, None)
    return None


# ── Low-level API request helper ──────────────────────────────────────────────

async def _spotify_get(endpoint: str, token: str, params: dict | None = None) -> dict:
    url = f'{_SPOTIFY_API_BASE}{endpoint}'
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers={'Authorization': f'Bearer {token}'},
            params=params or {},
        ) as resp:
            if resp.status == 204:
                return {}
            if resp.status == 401:
                return {'error': 'unauthorized'}
            if resp.status == 429:
                logger.warning(f'Spotify rate limited on {endpoint}')
                return {'error': 'rate_limited'}
            return await resp.json()


# ── Public (Client Credentials) calls ────────────────────────────────────────

async def search_track(query: str) -> dict | None:
    """Search Spotify for a track. Returns normalized track dict or None."""
    cache_key = f'search:{query.lower()}'
    cached = await db.get_music_cache(cache_key)
    if cached:
        return json.loads(cached['data_json'])

    token = await _get_app_token()
    data = await _spotify_get('/search', token, {'q': query, 'type': 'track', 'limit': 1})

    tracks = data.get('tracks', {}).get('items', [])
    if not tracks:
        return None

    t = tracks[0]
    result = {
        'id': t['id'],
        'name': t['name'],
        'artists': [a['name'] for a in t['artists']],
        'album': t['album']['name'],
        'album_art': t['album']['images'][0]['url'] if t['album']['images'] else None,
        'duration_ms': t['duration_ms'],
        'external_url': t['external_urls']['spotify'],
        'preview_url': t.get('preview_url'),
        'popularity': t.get('popularity', 0),
    }
    await db.set_music_cache(cache_key, json.dumps(result), config.MUSIC_CACHE_TTL['search'])
    return result


async def get_new_releases(limit: int = 8) -> list[dict]:
    """Fetch new album/single releases. Cached for 1 hour."""
    cached = await db.get_music_cache('newreleases')
    if cached:
        return json.loads(cached['data_json'])

    token = await _get_app_token()
    data = await _spotify_get('/browse/new-releases', token, {'limit': limit})

    albums = data.get('albums', {}).get('items', [])
    result = [
        {
            'name': a['name'],
            'artists': [ar['name'] for ar in a['artists']],
            'album_art': a['images'][0]['url'] if a['images'] else None,
            'external_url': a['external_urls']['spotify'],
            'release_date': a.get('release_date', ''),
            'type': a.get('album_type', 'album'),
        }
        for a in albums
    ]
    await db.set_music_cache('newreleases', json.dumps(result), config.MUSIC_CACHE_TTL['newreleases'])
    return result


# ── User (Authorization Code) calls ──────────────────────────────────────────

async def get_nowplaying(user_id: int) -> dict | None:
    """Get the user's currently playing track. Returns None if not linked."""
    token = await _get_valid_user_token(user_id)
    if not token:
        return None

    data = await _spotify_get('/me/player/currently-playing', token)
    if not data or data.get('error'):
        return {'is_playing': False}
    if data.get('currently_playing_type') != 'track':
        return {'is_playing': False}

    item = data.get('item')
    if not item:
        return {'is_playing': False}

    return {
        'is_playing': data.get('is_playing', False),
        'name': item['name'],
        'artists': [a['name'] for a in item['artists']],
        'album': item['album']['name'],
        'album_art': item['album']['images'][0]['url'] if item['album']['images'] else None,
        'external_url': item['external_urls']['spotify'],
        'progress_ms': data.get('progress_ms', 0),
        'duration_ms': item['duration_ms'],
    }


async def get_recent_tracks(user_id: int, limit: int = 10) -> list[dict]:
    """Get user's recently played tracks."""
    token = await _get_valid_user_token(user_id)
    if not token:
        return []

    data = await _spotify_get('/me/player/recently-played', token, {'limit': limit})
    items = data.get('items', [])
    return [
        {
            'name': item['track']['name'],
            'artists': [a['name'] for a in item['track']['artists']],
            'album_art': item['track']['album']['images'][0]['url'] if item['track']['album']['images'] else None,
            'external_url': item['track']['external_urls']['spotify'],
            'played_at': item.get('played_at', ''),
        }
        for item in items
    ]


async def get_top_artists(user_id: int, time_range: str = 'month', limit: int = 5) -> list[dict]:
    """Get user's top artists. time_range: week / month / all."""
    token = await _get_valid_user_token(user_id)
    if not token:
        return []

    tr = _TIME_RANGE_MAP.get(time_range, 'medium_term')
    data = await _spotify_get('/me/top/artists', token, {'time_range': tr, 'limit': limit})
    return [
        {
            'name': a['name'],
            'genres': a.get('genres', [])[:3],
            'image': a['images'][0]['url'] if a.get('images') else None,
            'external_url': a['external_urls']['spotify'],
            'followers': a.get('followers', {}).get('total', 0),
            'popularity': a.get('popularity', 0),
        }
        for a in data.get('items', [])
    ]


async def get_top_tracks(user_id: int, time_range: str = 'month', limit: int = 5) -> list[dict]:
    """Get user's top tracks. time_range: week / month / all."""
    token = await _get_valid_user_token(user_id)
    if not token:
        return []

    tr = _TIME_RANGE_MAP.get(time_range, 'medium_term')
    data = await _spotify_get('/me/top/tracks', token, {'time_range': tr, 'limit': limit})
    return [
        {
            'name': t['name'],
            'artists': [a['name'] for a in t['artists']],
            'album_art': t['album']['images'][0]['url'] if t['album']['images'] else None,
            'external_url': t['external_urls']['spotify'],
            'popularity': t.get('popularity', 0),
        }
        for t in data.get('items', [])
    ]


async def get_user_profile(user_id: int) -> dict | None:
    """Get the linked Spotify user's own profile (display name, image, followers)."""
    token = await _get_valid_user_token(user_id)
    if not token:
        return None
    data = await _spotify_get('/me', token)
    if data.get('error'):
        return None
    return {
        'display_name': data.get('display_name') or data.get('id', 'Unknown'),
        'id': data.get('id', ''),
        'image': data.get('images', [{}])[0].get('url') if data.get('images') else None,
        'followers': data.get('followers', {}).get('total', 0),
        'external_url': data.get('external_urls', {}).get('spotify', ''),
    }


# ── OAuth callback server ─────────────────────────────────────────────────────

_SUCCESS_HTML = """<!DOCTYPE html>
<html><head>
  <meta charset="utf-8">
  <title>Spotify Connected — Tainment+</title>
  <style>
    body{background:#121212;color:#fff;font-family:sans-serif;
         display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .card{background:#1db954;border-radius:16px;padding:40px 60px;text-align:center}
    h1{margin:0 0 12px;font-size:2rem} p{margin:0;opacity:.85}
  </style>
</head><body>
  <div class="card">
    <h1>Connected!</h1>
    <p>Your Spotify account is linked to Tainment+.<br>You can close this tab and return to Discord.</p>
  </div>
</body></html>"""

_ERROR_HTML = """<!DOCTYPE html>
<html><head>
  <meta charset="utf-8">
  <title>Error — Tainment+</title>
  <style>
    body{background:#121212;color:#fff;font-family:sans-serif;
         display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
    .card{background:#ed4245;border-radius:16px;padding:40px 60px;text-align:center}
    h1{margin:0 0 12px} p{margin:0;opacity:.85}
  </style>
</head><body>
  <div class="card">
    <h1>Authorization Failed</h1>
    <p>Something went wrong. Please try <code>t!spotify connect</code> again in Discord.</p>
  </div>
</body></html>"""


async def _oauth_callback(request: web.Request) -> web.Response:
    code = request.query.get('code')
    state = request.query.get('state')
    error = request.query.get('error')

    if error or not code or not state or state not in _pending_states:
        return web.Response(text=_ERROR_HTML, content_type='text/html')

    _pending_states.pop(state)
    try:
        token_data = await exchange_code(code)
        if 'access_token' not in token_data:
            logger.warning(f'Code exchange returned no token: {token_data}')
            return web.Response(text=_ERROR_HTML, content_type='text/html')
        _completed_tokens[state] = token_data
        return web.Response(text=_SUCCESS_HTML, content_type='text/html')
    except Exception:
        logger.exception('OAuth callback error')
        return web.Response(text=_ERROR_HTML, content_type='text/html')


class OAuthServer:
    """Tiny aiohttp web server that handles the Spotify OAuth redirect."""

    def __init__(self):
        self._runner: web.AppRunner | None = None

    async def start(self):
        if not config.SPOTIFY_CLIENT_ID:
            logger.warning('SPOTIFY_CLIENT_ID not set — OAuth server not started.')
            return
        app = web.Application()
        app.router.add_get('/spotify/callback', _oauth_callback)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, '0.0.0.0', config.SPOTIFY_OAUTH_PORT)
        await site.start()
        logger.info(f'Spotify OAuth server listening on port {config.SPOTIFY_OAUTH_PORT}')

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
