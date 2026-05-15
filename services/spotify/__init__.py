"""
services/spotify — Spotify integration service layer.

Phase 4: extracted from the old root-level music_api.py. Split into:
  - oauth.py  — token lifecycle, auth-URL builder, `_pending_states`, callback server
  - client.py — Spotify Web API HTTP client

The cog (spotify.py) does `import services.spotify as sp` and uses the
re-exported names below, exactly as it used `import music_api as sp` before.
This package IS the service layer — no Discord/cog code lives here.
"""
from .oauth import (  # noqa: F401
    OAuthServer,
    build_auth_url,
    wait_for_auth,
    exchange_code,
    _pending_states,
    _get_app_token,
    _get_valid_user_token,
)
from .client import (  # noqa: F401
    search_track,
    get_new_releases,
    get_nowplaying,
    get_recent_tracks,
    get_top_artists,
    get_top_tracks,
    get_user_profile,
)

__all__ = [
    "OAuthServer", "build_auth_url", "wait_for_auth", "exchange_code",
    "_pending_states", "_get_app_token", "_get_valid_user_token",
    "search_track", "get_new_releases", "get_nowplaying", "get_recent_tracks",
    "get_top_artists", "get_top_tracks", "get_user_profile",
]
