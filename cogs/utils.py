"""Phase 0 shim — re-exports setup() from the root-level utils module.

This shim exists so discord.py can load 'cogs.utils' as a dotted-path
extension while the real code stays at /utils.py. Phase 1+ will move the
implementation into cogs/utils/ and delete this file.
"""
from utils import setup  # noqa: F401
