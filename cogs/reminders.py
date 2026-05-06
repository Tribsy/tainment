"""Phase 0 shim — re-exports setup() from the root-level reminders module.

This shim exists so discord.py can load 'cogs.reminders' as a dotted-path
extension while the real code stays at /reminders.py. Phase 1+ will move the
implementation into cogs/reminders/ and delete this file.
"""
from reminders import setup  # noqa: F401
