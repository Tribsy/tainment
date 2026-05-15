"""
services/spotify/oauth.py — Spotify OAuth flow + callback web server.

Phase 4: extracted verbatim from music_api.py. Holds the app/user token
lifecycle (fetch, exchange, refresh, validate), the authorization-URL builder,
the in-memory `_pending_states` map that ties an OAuth `state` to a Discord
user id, and the aiohttp callback server that completes the flow.

`client.py` imports `_get_valid_user_token` and `_get_app_token` from here.
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

logger = logging.getLogger("tainment.spotify.oauth")


_pending_states: dict[str, int] = {}
_completed_tokens: dict[str, dict] = {}


_SPOTIFY_ACCOUNTS_URL = 'https://accounts.spotify.com/api/token'


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
