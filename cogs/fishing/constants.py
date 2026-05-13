"""
cogs/fishing/constants.py — fishing reward and color tables (per tier).

Phase 3d: extracted verbatim from cogs/fishing/__init__.py. Leaf module —
no internal imports.
"""


TIER_EMOJIS = {
    'trash': '🗑️', 'common': '🐟', 'uncommon': '🐠', 'rare': '🐡',
    'epic': '✨', 'legendary': '🌟', 'mythic': '💫', 'ancient': '🏺',
    'celestial': '🌠', 'void': '⬛',
}


TIER_COLORS = {
    'trash': 0x7f8c8d, 'common': 0x95a5a6, 'uncommon': 0x2ecc71,
    'rare': 0x3498db, 'epic': 0xe040fb, 'legendary': 0xf39c12,
    'mythic': 0x9b59b6, 'ancient': 0x8e44ad, 'celestial': 0x00e5ff,
    'void': 0x1a1a2e,
}


TIER_XP = {
    'trash': 2, 'common': 10, 'uncommon': 25, 'rare': 60,
    'epic': 120, 'legendary': 250, 'mythic': 400, 'ancient': 600,
    'celestial': 900, 'void': 1500,
}


TIER_GEMS = {
    'trash': 0, 'common': 0, 'uncommon': 0, 'rare': 1,
    'epic': 2, 'legendary': 5, 'mythic': 10, 'ancient': 20,
    'celestial': 50, 'void': 100,
}


TIER_TOKENS = {
    'trash': 0, 'common': 0, 'uncommon': 0, 'rare': 0,
    'epic': 1, 'legendary': 2, 'mythic': 4, 'ancient': 8,
    'celestial': 15, 'void': 30,
}
