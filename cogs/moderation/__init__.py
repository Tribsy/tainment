"""
cogs/moderation — Moderation package.

Phase 3e shape:
  - constants.py — MOD_COLORS embed palette
  - service.py   — case DB init/insert, log resolution, mod-embed factory, duration parser
  - commands.py  — Moderation cog (warn/kick/ban/timeout/purge/lock/slowmode/nick/roles/modlog)
  - __init__.py  — this file: re-exports setup()
"""
from .commands import setup  # noqa: F401  (discord.py extension loader entry point)

__all__ = ["setup"]
