"""
core/database/economy.py — coins/gems/tokens, daily streak, work cooldown, inventory.

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging


logger = logging.getLogger("tainment.database.economy")


async def init():
    """Create tables and run migrations for the economy domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 500,
                total_earned INTEGER DEFAULT 0,
                last_daily TIMESTAMP,
                daily_streak INTEGER DEFAULT 0,
                last_work TIMESTAMP,
                last_rob TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_key TEXT,
                quantity INTEGER DEFAULT 1,
                acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Migrations
        # Migrate: add gems/tokens columns if they don't exist yet
        for col in ('gems INTEGER DEFAULT 0', 'tokens INTEGER DEFAULT 0'):
            try:
                await db.execute(f"ALTER TABLE economy ADD COLUMN {col}")
            except Exception:
                pass  # column already exists
        # Migrate: add previous_daily_streak for streak_restore item
        try:
            await db.execute("ALTER TABLE economy ADD COLUMN previous_daily_streak INTEGER DEFAULT 0")
        except Exception:
            pass  # column already exists
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────

# -- Economy helpers --

async def get_balance(user_id: int) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT coins FROM economy WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def update_balance(user_id: int, amount: int):
    """Add (or subtract) coins. Floors at 0."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            UPDATE economy
            SET coins = MAX(0, coins + ?),
                total_earned = CASE WHEN ? > 0 THEN total_earned + ? ELSE total_earned END
            WHERE user_id = ?
        """, (amount, amount, amount, user_id))
        await db.commit()


async def get_economy(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM economy WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()


async def update_economy_field(user_id: int, **kwargs):
    if not kwargs:
        return
    fields = ', '.join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(f"UPDATE economy SET {fields} WHERE user_id = ?", values)
        await db.commit()


# -- Multi-currency helpers --

_VALID_CURRENCIES = ('coins', 'gems', 'tokens')


async def get_currency(user_id: int, currency: str) -> int:
    if currency not in _VALID_CURRENCIES:
        raise ValueError(f"Unknown currency: {currency}")
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            f"SELECT {currency} FROM economy WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def earn_currency(user_id: int, currency: str, amount: int):
    """Add amount to a currency (floors at 0). Also tracks total_earned for coins."""
    if currency not in _VALID_CURRENCIES or amount <= 0:
        return
    async with aiosqlite.connect(config.DB_PATH) as db:
        if currency == 'coins':
            await db.execute(
                "UPDATE economy SET coins = coins + ?, total_earned = total_earned + ? WHERE user_id = ?",
                (amount, amount, user_id)
            )
        else:
            await db.execute(
                f"UPDATE economy SET {currency} = {currency} + ? WHERE user_id = ?",
                (amount, user_id)
            )
        await db.commit()


async def spend_currency(user_id: int, currency: str, amount: int):
    """Subtract amount from a currency (floors at 0)."""
    if currency not in _VALID_CURRENCIES or amount <= 0:
        return
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            f"UPDATE economy SET {currency} = MAX(0, {currency} - ?) WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


# -- Inventory helpers --

async def get_inventory(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM inventory WHERE user_id = ? ORDER BY acquired_at DESC",
            (user_id,)
        ) as cur:
            return await cur.fetchall()


async def add_inventory_item(user_id: int, item_key: str, expires_at=None, allow_stack=False):
    async with aiosqlite.connect(config.DB_PATH) as db:
        # Check if non-expiring item already owned (skip for stackable consumables)
        if not allow_stack and expires_at is None:
            async with db.execute(
                "SELECT id FROM inventory WHERE user_id = ? AND item_key = ? AND expires_at IS NULL",
                (user_id, item_key)
            ) as cur:
                existing = await cur.fetchone()
            if existing:
                return False  # already owned
        await db.execute(
            "INSERT INTO inventory (user_id, item_key, expires_at) VALUES (?, ?, ?)",
            (user_id, item_key, expires_at)
        )
        await db.commit()
        return True


async def remove_inventory_item(user_id: int, item_key: str) -> bool:
    """Remove one instance of item_key from the user's inventory. Returns True if removed."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM inventory WHERE user_id = ? AND item_key = ? LIMIT 1",
            (user_id, item_key)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        await db.execute("DELETE FROM inventory WHERE id = ?", (row[0],))
        await db.commit()
        return True


async def has_active_item(user_id: int, item_key: str) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("""
            SELECT id FROM inventory
            WHERE user_id = ? AND item_key = ?
            AND (expires_at IS NULL OR expires_at > datetime('now'))
        """, (user_id, item_key)) as cur:
            return (await cur.fetchone()) is not None


# -- Level helpers --

