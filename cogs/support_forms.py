"""Phase 0 shim — re-exports setup() from the root-level support_forms module.

This shim exists so discord.py can load 'cogs.support_forms' as a dotted-path
extension while the real code stays at /support_forms.py. Phase 1+ will move the
implementation into cogs/support_forms/ and delete this file.
"""
from support_forms import setup  # noqa: F401
