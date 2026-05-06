"""Phase 0 shim — re-exports setup() from the root-level payment module.

This shim exists so discord.py can load 'cogs.payment' as a dotted-path
extension while the real code stays at /payment.py. Phase 1+ will move the
implementation into cogs/payment/ and delete this file.
"""
from payment import setup  # noqa: F401
