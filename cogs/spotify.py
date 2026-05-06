"""Phase 0 shim — re-exports setup() from the root-level spotify module.

This shim exists so discord.py can load 'cogs.spotify' as a dotted-path
extension while the real code stays at /spotify.py. Phase 1+ will move the
implementation into cogs/spotify/ and delete this file.
"""
from spotify import setup  # noqa: F401
