"""Phase 0 shim — re-exports setup() from the root-level profile module.

This shim exists so discord.py can load 'cogs.profile' as a dotted-path
extension while the real code stays at /profile.py. Phase 1+ will move the
implementation into cogs/profile/ and delete this file.
"""
from profile import setup  # noqa: F401
