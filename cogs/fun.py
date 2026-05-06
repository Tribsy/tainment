"""Phase 0 shim — re-exports setup() from the root-level fun module.

This shim exists so discord.py can load 'cogs.fun' as a dotted-path
extension while the real code stays at /fun.py. Phase 1+ will move the
implementation into cogs/fun/ and delete this file.
"""
from fun import setup  # noqa: F401
