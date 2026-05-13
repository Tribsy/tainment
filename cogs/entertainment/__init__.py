"""
cogs/entertainment — Entertainment package.

Phase 3g shape:
  - constants.py — JOKES/STORIES/HANGMAN data banks
  - service.py   — tier_check helper
  - views.py     — RPSView, TriviaView
  - commands.py  — Entertainment cog (joke, story, trivia, rps, hangman, etc.)
  - __init__.py  — re-exports setup()
"""
from .commands import setup  # noqa: F401

__all__ = ["setup"]
