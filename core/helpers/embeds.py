"""
core/helpers/embeds.py — embed factories for the four common semantic states.

Replaces the inline `discord.Embed(description=msg, color=config.COLORS['error'])`
pattern that exists in nearly every cog. Centralizes color choice so a future
theme change (e.g., dark-mode-friendly red) is one edit, not 40.

Conventions:
  - `description` is the primary message; required positionally for terseness.
  - `title` is optional; most short replies don't need one.
  - Each helper returns a `discord.Embed` ready to pass to `ctx.send(embed=...)`.

Usage:
    from core.helpers.embeds import error_embed, success_embed, info_embed, warn_embed
    await ctx.send(embed=error_embed("You don't own that item."))
    await ctx.send(embed=success_embed("Sent **500 coins** to @user."))
"""
import discord
import config


def error_embed(description: str, title: str | None = None) -> discord.Embed:
    """Red embed — for failures, validation errors, missing-resource cases."""
    return discord.Embed(title=title, description=description, color=config.COLORS["error"])


def success_embed(description: str, title: str | None = None) -> discord.Embed:
    """Green embed — for confirmations, completions, successful state changes."""
    return discord.Embed(title=title, description=description, color=config.COLORS["success"])


def info_embed(description: str, title: str | None = None) -> discord.Embed:
    """Primary-color embed — neutral info, status replies, plain content."""
    return discord.Embed(title=title, description=description, color=config.COLORS["primary"])


def warn_embed(description: str, title: str | None = None) -> discord.Embed:
    """Yellow embed — soft rejections, upgrade prompts, gentle nudges (e.g. tier gating)."""
    return discord.Embed(title=title, description=description, color=config.COLORS["warning"])
