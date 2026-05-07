"""
core/database/messages.py — persistent bot message IDs (live embeds).

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging


logger = logging.getLogger("tainment.database.messages")


async def init():
    """Create tables and run migrations for the messages domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_messages (
                guild_id INTEGER,
                purpose TEXT,
                channel_id INTEGER,
                message_id INTEGER,
                PRIMARY KEY (guild_id, purpose)
            )
        """)
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────

# -- Bot message helpers (live leaderboard, etc.) --

async def get_bot_message(guild_id: int, purpose: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM bot_messages WHERE guild_id = ? AND purpose = ?",
            (guild_id, purpose)
        ) as cur:
            return await cur.fetchone()



async def upsert_bot_message(guild_id: int, purpose: str, channel_id: int, message_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO bot_messages (guild_id, purpose, channel_id, message_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, purpose) DO UPDATE SET channel_id = ?, message_id = ?
        """, (guild_id, purpose, channel_id, message_id, channel_id, message_id))
        await db.commit()


# -- Spotify account helpers --

