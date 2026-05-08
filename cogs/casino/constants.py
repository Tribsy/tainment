"""
cogs/casino/constants.py — module-level constants for the casino package.

Phase 3a.2 step 2: extracted from cogs/casino/__init__.py to break the
circular-import dance between views.py and the package root.

Holds:
  - Asset paths derived from the repo root (assumes this file sits at
    cogs/casino/constants.py — two dirs deep from the repo root).
  - Config aliases C and CE for shorter game-logic code.

Game-tuning constants (slot symbols, wheel segments, payouts) still live in
config.CASINO. A future cleanup may move them here too.
"""
import os

import config


# ─── Asset paths ────────────────────────────────────────────────────────────
# This file is at cogs/casino/constants.py — walk up two levels to repo root,
# then into assets/.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
_ASSETS = os.path.join(_PROJECT_ROOT, "assets")
ROULETTE_TABLE_PATH = os.path.join(_ASSETS, "images", "roulette_table.png")
WHEEL_SPIN_PATH = os.path.join(_ASSETS, "gifs", "wheel_spin.gif")


# ─── Config aliases ─────────────────────────────────────────────────────────
C = config.CASINO              # game tuning, payouts, limits
CE = config.CURRENCY_EMOJI

# ─── Game data constants ────────────────────────────────────────────────────
SPIN_FRAMES = ["🌀", "🌪️", "💫", "⚡", "🌀"]
RED_NUMS = config.CASINO["roulette_red"]
CARD_NAMES = {1: "A", 11: "J", 12: "Q", 13: "K"}
# ─── Card data (blackjack, highlow) ─────────────────────────────────────────
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
