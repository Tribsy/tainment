"""
cogs/casino — Casino package.

Phase 3a.2 final shape:
  - constants.py — config aliases, asset paths, game data (SUITS/RANKS/SPIN_FRAMES/RED_NUMS/CARD_NAMES)
  - service.py — 20 game-logic + embed helpers (settle, run_slots, RNG, etc.)
  - views.py — 5 Discord UI Views (RouletteView, BlackjackView, HiLoView, BetModal, DuelAcceptView)
  - commands.py — Casino cog class + prefix-command adapters + setup()
  - __init__.py — this file: re-exports setup() so discord.py's load_extension('cogs.casino') finds it

Other cogs migrating in Phase 3b should follow this same shape.
"""
from .commands import setup  # noqa: F401  (discord.py extension loader entry point)

__all__ = ["setup"]
