"""Phase 0 shim — re-exports setup() from the root-level music_trivia module.

This shim exists so discord.py can load 'cogs.music_trivia' as a dotted-path
extension while the real code stays at /music_trivia.py. Phase 1+ will move the
implementation into cogs/music_trivia/ and delete this file.
"""
from music_trivia import setup  # noqa: F401
