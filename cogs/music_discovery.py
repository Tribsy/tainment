"""Phase 0 shim — re-exports setup() from the root-level music_discovery module.

This shim exists so discord.py can load 'cogs.music_discovery' as a dotted-path
extension while the real code stays at /music_discovery.py. Phase 1+ will move the
implementation into cogs/music_discovery/ and delete this file.
"""
from music_discovery import setup  # noqa: F401
