"""
services/spotify/client.py — Spotify Web API HTTP client.

Phase 4: extracted verbatim from music_api.py. Wraps the Spotify endpoints the
bot uses: track search, new releases, now-playing, recent tracks, top
artists/tracks, user profile. `_spotify_get` is the shared request helper.

Token acquisition is delegated to oauth.py — these functions never touch the
OAuth flow directly.
"""
import asyncio
import json
import logging
import time

import aiohttp

import config
import database as db

from .oauth import _get_app_token, _get_valid_user_token

logger = logging.getLogger("tainment.spotify.client")


_SPOTIFY_API_BASE = 'https://api.spotify.com/v1'


_TIME_RANGE_MAP = {'week': 'short_term', 'month': 'medium_term', 'all': 'long_term'}


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
