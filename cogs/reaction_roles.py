"""Phase 0 shim — re-exports setup() from the root-level reaction_roles module.

This shim exists so discord.py can load 'cogs.reaction_roles' as a dotted-path
extension while the real code stays at /reaction_roles.py. Phase 1+ will move the
implementation into cogs/reaction_roles/ and delete this file.
"""
from reaction_roles import setup  # noqa: F401
