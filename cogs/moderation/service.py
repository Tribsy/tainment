"""
cogs/moderation/service.py — moderation helpers.

Phase 3e: extracted verbatim from cogs/moderation/__init__.py. Holds the mod
case DB init/insert, log-channel resolution, the standard mod embed factory,
and the duration-string parser.
"""
import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import aiosqlite
import re

import config

from .constants import MOD_COLORS


__all__ = [
    "_init_mod_tables",
    "_add_case",
    "_get_log_channel",
    "_send_log",
    "_mod_embed",
    "_parse_duration",
]


# ─── Helper bodies (verbatim from source) ───────────────────────────────────

async def _init_mod_tables():
    """Create moderation tables if they don't exist."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mod_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                duration TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mod_settings (
                guild_id INTEGER PRIMARY KEY,
                log_channel_id INTEGER
            )
        """)
        await db.commit()


async def _add_case(guild_id, user_id, mod_id, action, reason=None, duration=None) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO mod_cases (guild_id, user_id, moderator_id, action, reason, duration) VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, user_id, mod_id, action, reason, duration)
        )
        await db.commit()
        return cur.lastrowid


async def _get_log_channel(bot: commands.Bot, guild_id: int) -> discord.TextChannel | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT log_channel_id FROM mod_settings WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row or not row[0]:
        return None
    guild = bot.get_guild(guild_id)
    return guild.get_channel(row[0]) if guild else None


async def _send_log(bot: commands.Bot, guild_id: int, embed: discord.Embed):
    ch = await _get_log_channel(bot, guild_id)
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.HTTPException:
            pass


def _mod_embed(action: str, user: discord.Member | discord.User, mod: discord.Member,
               reason: str, case_id: int, duration: str = None) -> discord.Embed:
    color = MOD_COLORS.get(action.lower(), config.COLORS['primary'])
    embed = discord.Embed(
        title=f"\U0001f6e1\ufe0f {action.capitalize()} | Case #{case_id}",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed.add_field(name="Moderator", value=mod.mention, inline=True)
    if duration:
        embed.add_field(name="Duration", value=duration, inline=True)
    embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"User ID: {user.id}")
    return embed


def _parse_duration(s: str) -> timedelta | None:
    """Parse strings like 10m, 2h, 1d, 30s into timedelta."""
    pattern = re.fullmatch(r'(\d+)([smhd])', s.lower().strip())
    if not pattern:
        return None
    val, unit = int(pattern.group(1)), pattern.group(2)
    if unit == 's':
        return timedelta(seconds=val)
    if unit == 'm':
        return timedelta(minutes=val)
    if unit == 'h':
        return timedelta(hours=val)
    if unit == 'd':
        return timedelta(days=val)
    return None
