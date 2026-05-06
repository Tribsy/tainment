"""Phase 0 shim — re-exports setup() from the root-level server_settings module.

This shim exists so discord.py can load 'cogs.server_settings' as a dotted-path
extension while the real code stays at /server_settings.py. Phase 1+ will move the
implementation into cogs/server_settings/ and delete this file.
"""
from server_settings import setup  # noqa: F401
