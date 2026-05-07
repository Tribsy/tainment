"""
core/permissions/tier_gate.py — canonical tier definitions + access decorator.

The bot has FOUR subscription tiers in ascending order: Basic < Vibe < Premium < Pro.
Before this module, six cogs each defined their own TIER_ORDER (some as dicts,
some as lists, sometimes with conflicting semantics). This module is the single
source of truth.

The `@require_tier(min_tier)` decorator wraps a command. If the user's tier is
below the threshold, the decorator sends a styled "upgrade required" embed and
short-circuits — the wrapped function never runs.

Cogs that already have a local TIER_ORDER + a homegrown gate function will
migrate to this module as they're touched. Don't mass-rewrite.
"""
from functools import wraps

import discord
from discord.ext import commands

import config
import database as db
from core.helpers.embeds import warn_embed


# ─── Canonical tier ordering ────────────────────────────────────────────────
# Index = position; lower = lower tier. Use comparisons via `meets_tier`.
TIER_ORDER: dict[str, int] = {
    "Basic":   0,
    "Vibe":    1,
    "Premium": 2,
    "Pro":     3,
}

TIERS: tuple[str, ...] = tuple(TIER_ORDER.keys())  # iterable form


def meets_tier(user_tier: str, required: str) -> bool:
    """Return True iff `user_tier` is at least as high as `required`.

    Both arguments must be valid tier names; raises KeyError on a typo, which
    is intentional — silent fall-through is far worse than a startup crash.
    """
    return TIER_ORDER[user_tier] >= TIER_ORDER[required]


# ─── Decorator ──────────────────────────────────────────────────────────────
def require_tier(min_tier: str):
    """Gate a (hybrid|prefix) command on a minimum subscription tier.

    Usage:
        @commands.hybrid_command(name='hangman', ...)
        @require_tier('Premium')
        async def hangman(self, ctx, ...):
            ...

    The wrapped function only runs if the caller's tier ≥ `min_tier`. Otherwise
    a yellow upgrade-prompt embed is sent and the body is skipped. The caller's
    tier is fetched via `database.get_tier()`; user is auto-`ensure_user`'d
    first so brand-new accounts don't 404 the lookup.

    NOTE on decorator order: Place @require_tier BELOW @commands.command (or
    @commands.hybrid_command) so the cog framework sees the right callable.
    Place ABOVE @commands.cooldown if used together — cooldowns should still
    consume on a tier rejection? Probably not, so order matters: tier_gate
    should reject before the cooldown decrements. Test combos before relying.
    """
    if min_tier not in TIER_ORDER:
        raise ValueError(f"require_tier: unknown tier {min_tier!r}; valid: {TIERS}")

    def decorator(func):
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            await db.ensure_user(ctx.author.id, ctx.author.name)
            user_tier = await db.get_tier(ctx.author.id)
            if not meets_tier(user_tier, min_tier):
                await ctx.send(embed=warn_embed(
                    f"This command requires **{min_tier}** or higher. "
                    f"You are currently on **{user_tier}**. "
                    f"Use `{config.COMMAND_PREFIX}subscribe` to upgrade.",
                    title="Upgrade required",
                ))
                return
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator
