"""Phase 0 shim — re-exports setup() from the root-level leaderboard module.

This shim exists so discord.py can load 'cogs.leaderboard' as a dotted-path
extension while the real code stays at /leaderboard.py. Phase 1+ will move the
implementation into cogs/leaderboard/ and delete this file.
"""
from leaderboard import setup  # noqa: F401
