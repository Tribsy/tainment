"""Phase 0 shim — re-exports setup() from the root-level automod module.

This shim exists so discord.py can load 'cogs.automod' as a dotted-path
extension while the real code stays at /automod.py. Phase 1+ will move the
implementation into cogs/automod/ and delete this file.
"""
from automod import setup  # noqa: F401
