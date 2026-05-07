"""
core/database/reminders.py — user reminders + due-poll helpers.

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging


logger = logging.getLogger("tainment.database.reminders")


async def init():
    """Create tables and run migrations for the reminders domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_id INTEGER,
                message TEXT,
                remind_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent BOOLEAN DEFAULT 0
            )
        """)
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────

# -- Reminder helpers --

async def create_reminder(user_id, channel_id, message, remind_at):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO reminders (user_id, channel_id, message, remind_at) VALUES (?, ?, ?, ?)",
            (user_id, channel_id, message, remind_at)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cur:
            return (await cur.fetchone())[0]


async def get_user_reminders(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM reminders WHERE user_id = ? AND sent = 0 ORDER BY remind_at ASC",
            (user_id,)
        ) as cur:
            return await cur.fetchall()


async def delete_reminder(reminder_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, user_id)
        ) as cur:
            if not await cur.fetchone():
                return False
        await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        await db.commit()
        return True


async def get_due_reminders():
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM reminders WHERE sent = 0 AND remind_at <= datetime('now')"
        ) as cur:
            return await cur.fetchall()


async def mark_reminder_sent(reminder_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
        await db.commit()


# -- Subscription report helpers --

