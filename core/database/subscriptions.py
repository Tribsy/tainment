"""
core/database/subscriptions.py — subscription tier, history, payments, usage tracking.

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging


logger = logging.getLogger("tainment.database.subscriptions")


async def init():
    """Create tables and run migrations for the subscriptions domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                tier TEXT DEFAULT 'Basic',
                start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP,
                grace_period_end TIMESTAMP,
                renewal_reminder_sent BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscription_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                old_tier TEXT,
                new_tier TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                changed_by INTEGER,
                reason TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                transaction_id TEXT,
                amount REAL,
                tier TEXT,
                duration_months INTEGER,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                feature TEXT,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────

async def get_subscription(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchone()


async def get_tier(user_id: int) -> str:
    sub = await get_subscription(user_id)
    if sub:
        return sub['tier']
    return 'Basic'


async def update_subscription(user_id: int, tier: str, end_date=None, grace_end=None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            UPDATE subscriptions
            SET tier = ?, end_date = ?, grace_period_end = ?, renewal_reminder_sent = 0
            WHERE user_id = ?
        """, (tier, end_date, grace_end, user_id))
        await db.commit()


async def log_subscription_change(user_id, old_tier, new_tier, changed_by=None, reason=None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO subscription_history (user_id, old_tier, new_tier, changed_by, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, old_tier, new_tier, changed_by, reason))
        await db.commit()


# -- Economy helpers --



async def get_subscriber_counts():
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT tier, COUNT(*) as count FROM subscriptions GROUP BY tier"
        ) as cur:
            return await cur.fetchall()


async def get_expiring_subscriptions(days: int = 3):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscriptions
            WHERE end_date IS NOT NULL
            AND end_date > datetime('now')
            AND end_date <= datetime('now', ? || ' days')
            AND tier != 'Basic'
            AND renewal_reminder_sent = 0
        """, (str(days),)) as cur:
            return await cur.fetchall()


async def get_grace_period_subscriptions():
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscriptions
            WHERE end_date IS NOT NULL
            AND end_date <= datetime('now')
            AND (grace_period_end IS NULL OR grace_period_end <= datetime('now'))
            AND tier != 'Basic'
        """) as cur:
            return await cur.fetchall()


async def mark_renewal_reminder_sent(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE subscriptions SET renewal_reminder_sent = 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def get_all_subscribers(tier: str = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if tier:
            async with db.execute(
                "SELECT s.*, u.username FROM subscriptions s JOIN users u ON s.user_id = u.user_id WHERE s.tier = ?",
                (tier,)
            ) as cur:
                return await cur.fetchall()
        async with db.execute(
            "SELECT s.*, u.username FROM subscriptions s JOIN users u ON s.user_id = u.user_id"
        ) as cur:
            return await cur.fetchall()


async def get_subscription_history(user_id: int, limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscription_history
            WHERE user_id = ?
            ORDER BY changed_at DESC
            LIMIT ?
        """, (user_id, limit)) as cur:
            return await cur.fetchall()


async def get_payment_history(user_id: int, limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM payments
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit)) as cur:
            return await cur.fetchall()


async def record_payment(user_id, transaction_id, amount, tier, duration_months, status):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO payments (user_id, transaction_id, amount, tier, duration_months, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, transaction_id, amount, tier, duration_months, status))
        await db.commit()


async def complete_payment(transaction_id: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            UPDATE payments SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ?
        """, (transaction_id,))
        await db.commit()


async def log_usage(user_id: int, feature: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO usage_stats (user_id, feature) VALUES (?, ?)",
            (user_id, feature)
        )
        await db.commit()


# -- Fishing helpers --

