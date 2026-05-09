"""
cogs/server_settings — Server Settings package.

Phase 3c shape (matches casino/shop template):
  - constants.py — server-template definitions used by `t!setupserver`
  - service.py   — async DB helpers + private setup-orchestrator
  - commands.py  — ServerSettings cog class + setup()
  - __init__.py  — this file: re-exports setup() AND public helpers

Other cogs that need these helpers should `from cogs.server_settings import X`
where X is one of: get_prefix, set_prefix, get_server_settings, ensure_server,
update_server_setting, is_command_enabled, set_command_toggle, get_afk, set_afk,
clear_afk, get_server_tier.
"""
from .commands import setup  # noqa: F401  (discord.py extension loader entry point)

# External-compat re-exports — keep the public helpers reachable at the
# package root so callers like `from cogs.server_settings import get_server_tier`
# work. Don't re-export private (underscore-prefixed) helpers.
from .service import (  # noqa: F401
    get_prefix,
    set_prefix,
    get_server_settings,
    ensure_server,
    update_server_setting,
    is_command_enabled,
    set_command_toggle,
    get_afk,
    set_afk,
    clear_afk,
    get_server_tier,
)

__all__ = [
    "setup",
    "get_prefix", "set_prefix",
    "get_server_settings", "ensure_server", "update_server_setting",
    "is_command_enabled", "set_command_toggle",
    "get_afk", "set_afk", "clear_afk",
    "get_server_tier",
]
