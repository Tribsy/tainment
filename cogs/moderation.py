"""Phase 0 shim — re-exports setup() from the root-level moderation module.

This shim exists so discord.py can load 'cogs.moderation' as a dotted-path
extension while the real code stays at /moderation.py. Phase 1+ will move the
implementation into cogs/moderation/ and delete this file.
"""
from moderation import setup  # noqa: F401
