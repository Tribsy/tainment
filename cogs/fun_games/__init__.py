"""
cogs/fun_games — Fun Games package.

Phase 3h shape (simplest variant — no helpers, no views):
  - constants.py — typerace/riddle/wyr/emoji/chain data banks
  - commands.py  — FunGames cog
  - __init__.py  — re-exports setup()
"""
from .commands import setup  # noqa: F401

__all__ = ["setup"]
