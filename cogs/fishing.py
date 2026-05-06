"""Phase 0 shim — re-exports setup() from the root-level fishing module.

This shim exists so discord.py can load 'cogs.fishing' as a dotted-path
extension while the real code stays at /fishing.py. Phase 1+ will move the
implementation into cogs/fishing/ and delete this file.
"""
from fishing import setup  # noqa: F401
