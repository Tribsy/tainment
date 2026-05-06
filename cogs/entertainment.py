"""Phase 0 shim — re-exports setup() from the root-level entertainment module.

This shim exists so discord.py can load 'cogs.entertainment' as a dotted-path
extension while the real code stays at /entertainment.py. Phase 1+ will move the
implementation into cogs/entertainment/ and delete this file.
"""
from entertainment import setup  # noqa: F401
