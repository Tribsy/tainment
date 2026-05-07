"""
core/database/polls.py — polls and feature-request votes.

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging


logger = logging.getLogger("tainment.database.polls")


async def init():
    """Create tables and run migrations for the polls domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                host_id INTEGER,
                question TEXT,
                options TEXT,
                ends_at TIMESTAMP,
                ended BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS feature_votes (
                message_id INTEGER,
                user_id INTEGER,
                vote INTEGER,
                PRIMARY KEY (message_id, user_id)
            )
        """)
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────


async def get_user_vote(message_id: int, user_id: int) -> int | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT vote FROM feature_votes WHERE message_id = ? AND user_id = ?",
            (message_id, user_id)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def set_feature_vote(message_id: int, user_id: int, vote: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO feature_votes (message_id, user_id, vote)
            VALUES (?, ?, ?)
            ON CONFLICT(message_id, user_id) DO UPDATE SET vote = ?
        """, (message_id, user_id, vote, vote))
        await db.commit()


async def remove_feature_vote(message_id: int, user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM feature_votes WHERE message_id = ? AND user_id = ?",
            (message_id, user_id)
        )
        await db.commit()


async def get_vote_counts(message_id: int) -> tuple[int, int]:
    """Returns (upvotes, downvotes)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT SUM(CASE WHEN vote=1 THEN 1 ELSE 0 END), SUM(CASE WHEN vote=-1 THEN 1 ELSE 0 END) FROM feature_votes WHERE message_id = ?",
            (message_id,)
        ) as cur:
            row = await cur.fetchone()
            return (row[0] or 0, row[1] or 0)


