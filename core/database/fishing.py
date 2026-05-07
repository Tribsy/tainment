"""
core/database/fishing.py — fishing stats, fish bag, fishing leaderboard.

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging


logger = logging.getLogger("tainment.database.fishing")


async def init():
    """Create tables and run migrations for the fishing domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fishing_stats (
                user_id INTEGER PRIMARY KEY,
                total_caught INTEGER DEFAULT 0,
                total_value INTEGER DEFAULT 0,
                biggest_catch_type TEXT,
                biggest_catch_coins INTEGER DEFAULT 0,
                fishing_xp INTEGER DEFAULT 0,
                fishing_level INTEGER DEFAULT 0,
                last_fished TIMESTAMP,
                equipped_rod TEXT DEFAULT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS fish_inventory (
                user_id INTEGER,
                fish_key TEXT,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, fish_key)
            )
        """)

        # Migrations
        # Migration: add equipped_rod column if missing (for existing databases)
        try:
            await db.execute("ALTER TABLE fishing_stats ADD COLUMN equipped_rod TEXT DEFAULT NULL")
            await db.commit()
        except Exception:
            pass  # Column already exists
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────

# -- Fishing helpers --

async def ensure_fishing_row(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO fishing_stats (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()


async def get_fishing_stats(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM fishing_stats WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchone()


async def update_fishing_stats(user_id: int, **kwargs):
    if not kwargs:
        return
    fields = ', '.join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            f"UPDATE fishing_stats SET {fields} WHERE user_id = ?", values
        )
        await db.commit()


async def add_fish_to_bag(user_id: int, fish_key: str, quantity: int = 1):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO fish_inventory (user_id, fish_key, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, fish_key) DO UPDATE SET quantity = quantity + ?
        """, (user_id, fish_key, quantity, quantity))
        await db.commit()


async def get_fish_inventory(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT fish_key, quantity FROM fish_inventory WHERE user_id = ? AND quantity > 0 ORDER BY fish_key",
            (user_id,)
        ) as cur:
            return await cur.fetchall()


async def sell_fish_from_bag(user_id: int, fish_key: str, quantity: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE fish_inventory SET quantity = MAX(0, quantity - ?) WHERE user_id = ? AND fish_key = ?",
            (quantity, user_id, fish_key)
        )
        await db.commit()


async def get_fishing_leaderboard(limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT f.user_id, f.total_caught, f.total_value, u.username
            FROM fishing_stats f
            LEFT JOIN users u ON f.user_id = u.user_id
            WHERE f.total_caught > 0
            ORDER BY f.total_value DESC
            LIMIT ?
        """, (limit,)) as cur:
            return await cur.fetchall()


# -- Bot message helpers (live leaderboard, etc.) --

