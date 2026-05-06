"""Phase 0 shim — re-exports setup() from the root-level shop module.

This shim exists so discord.py can load 'cogs.shop' as a dotted-path
extension while the real code stays at /shop.py. Phase 1+ will move the
implementation into cogs/shop/ and delete this file.
"""
from shop import setup  # noqa: F401
