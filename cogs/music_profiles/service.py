"""
cogs/music_profiles/service.py — music profile helpers + DB init.

Phase 3f: extracted verbatim from cogs/music_profiles/__init__.py.
"""
import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime, timezone, timedelta

import config
import database as db
import music_data as md

from .constants import TIER_ORDER, MAX_ARTISTS, MAX_PLAYLISTS


__all__ = [
    "_tier_gte",
    "_locked_embed",
    "_ensure_music_profile",
    "_get_music_profile",
    "_update_streak",
    "_init_music_tables",
]


# ─── Helper bodies (verbatim from source) ───────────────────────────────────

def _tier_gte(user_tier: str, required: str) -> bool:
    return TIER_ORDER.index(user_tier) >= TIER_ORDER.index(required)


def _locked_embed(required: str) -> discord.Embed:
    return discord.Embed(
        title="\U0001f512 Feature Locked",
        description=f"This command requires **{required}** tier or higher.\nUpgrade with `t!subscribe`.",
        color=config.COLORS['error'],
    )


async def _ensure_music_profile(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO music_profiles (user_id) VALUES (?)", (user_id,)
        )
        await conn.commit()


async def _get_music_profile(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM music_profiles WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchone()


async def _update_streak(user_id: int):
    """Increment music activity streak if last activity was within 48h, else reset."""
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT listening_streak, last_music_activity FROM music_profiles WHERE user_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return

        now = datetime.now(timezone.utc)
        last = row['last_music_activity']
        streak = row['listening_streak'] or 0

        if last:
            try:
                last_dt = datetime.fromisoformat(last.replace('Z', '+00:00'))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                diff = now - last_dt
                if diff < timedelta(hours=48):
                    streak += 1
                else:
                    streak = 1
            except Exception:
                streak = 1
        else:
            streak = 1

        await conn.execute("""
            UPDATE music_profiles
            SET listening_streak = ?, last_music_activity = datetime('now'),
                total_activities = total_activities + 1
            WHERE user_id = ?
        """, (streak, user_id))
        await conn.commit()


async def _init_music_tables():
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_profiles (
                user_id INTEGER PRIMARY KEY,
                favourite_genre TEXT,
                listening_streak INTEGER DEFAULT 0,
                last_music_activity TIMESTAMP,
                total_activities INTEGER DEFAULT 0,
                total_music_coins INTEGER DEFAULT 0,
                total_music_gems INTEGER DEFAULT 0,
                total_music_tokens INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_favourite_artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                artist TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_shared_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                song TEXT,
                artist TEXT,
                shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                name TEXT,
                is_public INTEGER DEFAULT 1,
                collab_user INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS music_playlist_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER,
                song TEXT,
                artist TEXT,
                added_by INTEGER,
                position INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES music_playlists(id)
            )
        """)
        await conn.commit()
