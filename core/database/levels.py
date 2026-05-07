"""
core/database/levels.py — XP and per-guild level state (level math helpers in core/helpers/levels.py).

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging

from core.helpers.levels import _calc_level, xp_for_next_level

logger = logging.getLogger("tainment.database.levels")


async def init():
    """Create tables and run migrations for the levels domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS levels (
                user_id INTEGER,
                guild_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                last_message TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────

# -- Level helpers --

async def get_level_data(user_id: int, guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM levels WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cur:
            return await cur.fetchone()


async def ensure_level_row(user_id: int, guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO levels (user_id, guild_id) VALUES (?, ?)",
            (user_id, guild_id)
        )
        await db.commit()


async def add_xp(user_id: int, guild_id: int, xp: int) -> dict:
    """
    Add XP to user. Returns dict with leveled_up, old_level, new_level.
    """
    await ensure_level_row(user_id, guild_id)
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cur:
            row = await cur.fetchone()
        old_xp = row['xp']
        old_level = row['level']
        new_xp = old_xp + xp
        new_level = _calc_level(new_xp)
        await db.execute(
            "UPDATE levels SET xp = ?, level = ?, last_message = datetime('now') WHERE user_id = ? AND guild_id = ?",
            (new_xp, new_level, user_id, guild_id)
        )
        await db.commit()
    return {
        'leveled_up': new_level > old_level,
        'old_level': old_level,
        'new_level': new_level,
        'xp': new_xp,
    }





async def get_level_leaderboard(guild_id: int, limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, xp, level
            FROM levels
            WHERE guild_id = ?
            ORDER BY xp DESC
            LIMIT ?
        """, (guild_id, limit)) as cur:
            return await cur.fetchall()


# -- Game score helpers --

