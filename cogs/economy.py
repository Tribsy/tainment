"""Phase 0 shim — re-exports setup() from the root-level economy module.

This shim exists so discord.py can load 'cogs.economy' as a dotted-path
extension while the real code stays at /economy.py. Phase 1+ will move the
implementation into cogs/economy/ and delete this file.
"""
from economy import setup  # noqa: F401
