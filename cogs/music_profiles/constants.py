"""
cogs/music_profiles/constants.py — music profile limits + local tier ordering.

Phase 3f: extracted verbatim from cogs/music_profiles/__init__.py.

Note: TIER_ORDER here duplicates `core.permissions.tier_gate.TIER_ORDER`. The
canonical version should eventually be imported from there. For this verbatim
move, the local copy stays — that's a follow-up cleanup, not a regression.
"""


TIER_ORDER = ['Basic', 'Vibe', 'Premium', 'Pro']


MAX_ARTISTS = {'Basic': 5, 'Vibe': 10, 'Premium': 15, 'Pro': 999}


MAX_PLAYLISTS = {'Basic': 0, 'Vibe': 3, 'Premium': 5, 'Pro': 999}
