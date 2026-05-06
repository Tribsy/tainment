"""Phase 0 shim — re-exports setup() from the root-level fun_games module.

This shim exists so discord.py can load 'cogs.fun_games' as a dotted-path
extension while the real code stays at /fun_games.py. Phase 1+ will move the
implementation into cogs/fun_games/ and delete this file.
"""
from fun_games import setup  # noqa: F401
