"""
core/helpers/levels.py — pure-math level helpers.

Extracted from database.py in Phase 1.5. These functions touch no I/O — they
compute level from XP and reverse. Belong in helpers, not the DB layer.
"""
import config


def _calc_level(xp: int) -> int:
    level = 0
    needed = config.LEVELS['xp_base']
    while xp >= needed:
        xp -= needed
        level += 1
        needed = int(needed * config.LEVELS['xp_factor'])
    return level


def xp_for_next_level(current_level: int) -> int:
    needed = config.LEVELS['xp_base']
    for _ in range(current_level):
        needed = int(needed * config.LEVELS['xp_factor'])
    return needed

