"""
cogs/shop — Shop package.

Phase 3b.2 final shape (matches casino template):
  - constants.py — SHOP registry, currency emojis, consumable keys, mystery prizes
  - service.py   — purchase flows, mystery box, item application helpers
  - views.py     — 3-section currency selector dropdown
  - commands.py  — Shop cog class + setup()
  - __init__.py  — this file: re-exports setup() AND SHOP (for external imports)

External code that does `from cogs.shop import SHOP` (e.g., profile.py) keeps
working through the re-export below.
"""
from .commands import setup  # noqa: F401  (discord.py extension loader entry point)
from .constants import SHOP  # noqa: F401  (external compatibility — profile.py)

__all__ = ["setup", "SHOP"]
