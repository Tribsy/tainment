"""
core/database/giveaways.py — giveaway records and per-user entries.

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging


logger = logging.getLogger("tainment.database.giveaways")


async def init():
    """Create tables and run migrations for the giveaways domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                host_id INTEGER,
                prize TEXT,
                winner_count INTEGER DEFAULT 1,
                end_time TIMESTAMP,
                ended BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_entries (
                giveaway_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (giveaway_id, user_id),
                FOREIGN KEY (giveaway_id) REFERENCES giveaways(id)
            )
        """)
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────

# -- Giveaway helpers --

async def create_giveaway(guild_id, channel_id, message_id, host_id, prize, winner_count, end_time):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO giveaways (guild_id, channel_id, message_id, host_id, prize, winner_count, end_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (guild_id, channel_id, message_id, host_id, prize, winner_count, end_time))
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cur:
            return (await cur.fetchone())[0]


async def get_giveaway(giveaway_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM giveaways WHERE id = ?", (giveaway_id,)) as cur:
            return await cur.fetchone()


async def get_giveaway_by_message(message_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM giveaways WHERE message_id = ?", (message_id,)
        ) as cur:
            return await cur.fetchone()


async def add_giveaway_entry(giveaway_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)",
                (giveaway_id, user_id)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_giveaway_entry(giveaway_id: int, user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?",
            (giveaway_id, user_id)
        )
        await db.commit()


async def get_giveaway_entries(giveaway_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?", (giveaway_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def end_giveaway(giveaway_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE giveaways SET ended = 1 WHERE id = ?", (giveaway_id,)
        )
        await db.commit()


async def get_active_giveaways():
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM giveaways WHERE ended = 0 AND end_time <= datetime('now')"
        ) as cur:
            return await cur.fetchall()


# -- Reminder helpers --

