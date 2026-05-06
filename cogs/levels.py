"""Phase 0 shim — re-exports setup() from the root-level levels module.

This shim exists so discord.py can load 'cogs.levels' as a dotted-path
extension while the real code stays at /levels.py. Phase 1+ will move the
implementation into cogs/levels/ and delete this file.
"""
from levels import setup  # noqa: F401
