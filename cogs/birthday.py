"""Phase 0 shim — re-exports setup() from the root-level birthday module.

This shim exists so discord.py can load 'cogs.birthday' as a dotted-path
extension while the real code stays at /birthday.py. Phase 1+ will move the
implementation into cogs/birthday/ and delete this file.
"""
from birthday import setup  # noqa: F401
