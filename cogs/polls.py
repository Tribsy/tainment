"""Phase 0 shim — re-exports setup() from the root-level polls module.

This shim exists so discord.py can load 'cogs.polls' as a dotted-path
extension while the real code stays at /polls.py. Phase 1+ will move the
implementation into cogs/polls/ and delete this file.
"""
from polls import setup  # noqa: F401
