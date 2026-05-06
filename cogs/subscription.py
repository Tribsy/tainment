"""Phase 0 shim — re-exports setup() from the root-level subscription module.

This shim exists so discord.py can load 'cogs.subscription' as a dotted-path
extension while the real code stays at /subscription.py. Phase 1+ will move the
implementation into cogs/subscription/ and delete this file.
"""
from subscription import setup  # noqa: F401
