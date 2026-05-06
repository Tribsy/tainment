"""Phase 0 shim — re-exports setup() from the root-level admin_subscription module.

This shim exists so discord.py can load 'cogs.admin_subscription' as a dotted-path
extension while the real code stays at /admin_subscription.py. Phase 1+ will move the
implementation into cogs/admin_subscription/ and delete this file.
"""
from admin_subscription import setup  # noqa: F401
