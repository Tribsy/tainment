"""
cogs/music_profiles — Music Profiles package.

Phase 3f shape:
  - constants.py — TIER_ORDER (local copy), MAX_ARTISTS, MAX_PLAYLISTS limits
  - service.py   — profile helpers + DB init for music_profiles tables
  - commands.py  — MusicProfiles cog
  - __init__.py  — re-exports setup()
"""
from .commands import setup  # noqa: F401

__all__ = ["setup"]
