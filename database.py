import aiosqlite
import logging
import config

logger = logging.getLogger('tainment.db')


async def init_db():
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # Users
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Subscriptions
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

        # Subscription history
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

        # Payments
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

        # Usage stats
        await db.execute("""
            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                feature TEXT,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Game scores
        await db.execute("""
            CREATE TABLE IF NOT EXISTS game_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                game TEXT,
                score INTEGER,
                achieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Story progress
        await db.execute("""
            CREATE TABLE IF NOT EXISTS story_progress (
                user_id INTEGER,
                story_key TEXT,
                part INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, story_key),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Economy
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

        # Inventory
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

        # Levels
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

        # Giveaways
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

        # Giveaway entries
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_entries (
                giveaway_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (giveaway_id, user_id),
                FOREIGN KEY (giveaway_id) REFERENCES giveaways(id)
            )
        """)

        # Polls
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

        # Reminders
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

        # Feature request votes
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feature_votes (
                message_id INTEGER,
                user_id INTEGER,
                vote INTEGER,
                PRIMARY KEY (message_id, user_id)
            )
        """)

        # Fishing stats
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
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Fish inventory
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fish_inventory (
                user_id INTEGER,
                fish_key TEXT,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, fish_key)
            )
        """)

        # Bot messages (persistent message IDs for live embeds)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_messages (
                guild_id INTEGER,
                purpose TEXT,
                channel_id INTEGER,
                message_id INTEGER,
                PRIMARY KEY (guild_id, purpose)
            )
        """)

        # Migrate: add gems/tokens columns if they don't exist yet
        for col in ('gems INTEGER DEFAULT 0', 'tokens INTEGER DEFAULT 0'):
            col_name = col.split()[0]
            try:
                await db.execute(f"ALTER TABLE economy ADD COLUMN {col}")
            except Exception:
                pass  # column already exists

        await db.commit()
        logger.info("Database initialized successfully.")


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


async def add_inventory_item(user_id: int, item_key: str, expires_at=None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        # Check if non-expiring item already owned
        if expires_at is None:
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


async def has_active_item(user_id: int, item_key: str) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("""
            SELECT id FROM inventory
            WHERE user_id = ? AND item_key = ?
            AND (expires_at IS NULL OR expires_at > datetime('now'))
        """, (user_id, item_key)) as cur:
            return (await cur.fetchone()) is not None


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


def _calc_level(xp: int) -> int:
    level = 0
    needed = config.LEVELS['xp_base']
    while xp >= needed:
        xp -= needed
        level += 1
        needed = int(needed * config.LEVELS['xp_factor'])
    return level


def xp_for_next_level(current_level: int) -> int:
    needed = config.LEVELS['xp_base']
    for _ in range(current_level):
        needed = int(needed * config.LEVELS['xp_factor'])
    return needed


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

async def record_score(user_id: int, game: str, score: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        # Only keep personal best
        async with db.execute(
            "SELECT score FROM game_scores WHERE user_id = ? AND game = ?",
            (user_id, game)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO game_scores (user_id, game, score) VALUES (?, ?, ?)",
                (user_id, game, score)
            )
        elif score > row[0]:
            await db.execute(
                "UPDATE game_scores SET score = ?, achieved_at = CURRENT_TIMESTAMP WHERE user_id = ? AND game = ?",
                (score, user_id, game)
            )
        await db.commit()


async def get_game_leaderboard(game: str, limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT g.user_id, g.score, u.username
            FROM game_scores g
            LEFT JOIN users u ON g.user_id = u.user_id
            WHERE g.game = ?
            ORDER BY g.score DESC
            LIMIT ?
        """, (game, limit)) as cur:
            return await cur.fetchall()


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

async def get_bot_message(guild_id: int, purpose: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM bot_messages WHERE guild_id = ? AND purpose = ?",
            (guild_id, purpose)
        ) as cur:
            return await cur.fetchone()


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


async def upsert_bot_message(guild_id: int, purpose: str, channel_id: int, message_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO bot_messages (guild_id, purpose, channel_id, message_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, purpose) DO UPDATE SET channel_id = ?, message_id = ?
        """, (guild_id, purpose, channel_id, message_id, channel_id, message_id))
        await db.commit()
