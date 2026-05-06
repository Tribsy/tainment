"""Phase 0 shim — re-exports setup() from the root-level giveaway module.

This shim exists so discord.py can load 'cogs.giveaway' as a dotted-path
extension while the real code stays at /giveaway.py. Phase 1+ will move the
implementation into cogs/giveaway/ and delete this file.
"""
from giveaway import setup  # noqa: F401
