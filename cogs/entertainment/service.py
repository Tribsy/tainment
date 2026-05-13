"""
cogs/entertainment/service.py — entertainment helpers.

Phase 3g: extracted verbatim from cogs/entertainment/__init__.py. Currently
just the `tier_check` helper; future helpers from the cog body can migrate
here as they're identified.
"""
import config
import database as db


__all__ = [
    "tier_check",
]


# ─── Helper bodies (verbatim from source) ───────────────────────────────────

def tier_check(tier: str, allowed_tiers: list[str]) -> bool:
    order = ['Basic', 'Vibe', 'Premium', 'Pro']
    try:
        return order.index(tier) >= min(order.index(t) for t in allowed_tiers)
    except ValueError:
        return False
