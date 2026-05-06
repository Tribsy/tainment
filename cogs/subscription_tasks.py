"""Phase 0 shim — re-exports setup() from the root-level subscription_tasks module.

This shim exists so discord.py can load 'cogs.subscription_tasks' as a dotted-path
extension while the real code stays at /subscription_tasks.py. Phase 1+ will move the
implementation into cogs/subscription_tasks/ and delete this file.
"""
from subscription_tasks import setup  # noqa: F401
