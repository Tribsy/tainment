"""
core/database/users.py — users + per-user metadata (bio).

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging


logger = logging.getLogger("tainment.database.users")


async def init():
    """Create tables and run migrations for the users domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migrations
        try:
            await db.execute("ALTER TABLE users ADD COLUMN bio TEXT")
        except Exception:
            pass  # column already exists
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────

# -- User helpers --

async def ensure_user(user_id: int, username: str = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username or str(user_id))
        )
        await db.execute(
            "INSERT OR IGNORE INTO subscriptions (user_id, tier) VALUES (?, 'Basic')",
            (user_id,)
        )
        await db.execute(
            "INSERT OR IGNORE INTO economy (user_id, coins) VALUES (?, ?)",
            (user_id, config.ECONOMY['starting_coins'])
        )
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()


