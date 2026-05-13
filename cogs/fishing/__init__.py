"""
cogs/fishing — Fishing package.

Phase 3d shape (matches casino/shop/server_settings template, with the optional
`data.py` module the roadmap allowed for static registries):
  - data.py      — FISH/TIERS/RODS registry + look-up helpers (1667 lines, mostly data)
  - constants.py — per-tier reward/color tables
  - service.py   — fishing business logic
  - commands.py  — Fishing cog class + setup()
  - __init__.py  — this file: re-exports setup() AND the data registry so
                   external callers (shop) can `from cogs.fishing import RODS`

External-compat: shop currently imports RODS from this package's namespace.
"""
from .commands import setup  # noqa: F401  (discord.py extension loader entry point)

# External-compat re-exports — keep the FISH/TIERS/RODS registry reachable at
# the package root so callers like `from cogs.fishing import RODS` work.
from .data import (  # noqa: F401
    FISH,
    TIERS,
    RODS,
    get_fish_count,
    get_tier_for_fish,
    can_catch_with_rod,
    get_catchable_tiers,
    get_rod_info,
    get_tier_weight_table,
)

__all__ = [
    "setup",
    "FISH", "TIERS", "RODS",
    "get_fish_count", "get_tier_for_fish", "can_catch_with_rod",
    "get_catchable_tiers", "get_rod_info", "get_tier_weight_table",
]
