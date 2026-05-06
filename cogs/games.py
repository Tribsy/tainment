"""Phase 0 shim — re-exports setup() from the root-level games module.

This shim exists so discord.py can load 'cogs.games' as a dotted-path
extension while the real code stays at /games.py. Phase 1+ will move the
implementation into cogs/games/ and delete this file.
"""
from games import setup  # noqa: F401
