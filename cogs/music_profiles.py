"""Phase 0 shim — re-exports setup() from the root-level music_profiles module.

This shim exists so discord.py can load 'cogs.music_profiles' as a dotted-path
extension while the real code stays at /music_profiles.py. Phase 1+ will move the
implementation into cogs/music_profiles/ and delete this file.
"""
from music_profiles import setup  # noqa: F401
