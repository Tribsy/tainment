"""Phase 0 shim — re-exports setup() from the root-level casino module.

This shim exists so discord.py can load 'cogs.casino' as a dotted-path
extension while the real code stays at /casino.py. Phase 1+ will move the
implementation into cogs/casino/ and delete this file.
"""
from casino import setup  # noqa: F401
