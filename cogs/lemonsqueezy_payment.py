"""Phase 0 shim — re-exports setup() from the root-level lemonsqueezy_payment module.

This shim exists so discord.py can load 'cogs.lemonsqueezy_payment' as a dotted-path
extension while the real code stays at /lemonsqueezy_payment.py. Phase 1+ will move the
implementation into cogs/lemonsqueezy_payment/ and delete this file.
"""
from lemonsqueezy_payment import setup  # noqa: F401
