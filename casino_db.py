"""
casino_db.py  –  Database helpers for the Casino system.

Call `casino_init_db()` once at startup (add it alongside `init_db()` in
main.py's setup_hook).  All other helpers are async and safe to call from
anywhere in the casino cog.
"""

import aiosqlite
import config
import logging
from datetime import datetime, timezone

logger = logging.getLogger("tainment.casino_db")


# ─────────────────────────────────────────────────────────────────────────────
# Table creation / migration
# ─────────────────────────────────────────────────────────────────────────────

async def casino_init_db():
    """Create casino tables if they don't exist, run safe migrations."""
    async with aiosqlite.connect(config.DB_PATH) as db:

        # casino_bank  –  single-row house bank
        await db.execute("""
            CREATE TABLE IF NOT EXISTS casino_bank (
                id                INTEGER PRIMARY KEY DEFAULT 1,
                balance           INTEGER DEFAULT 0,
                total_collected   INTEGER DEFAULT 0,
                total_paid_out    INTEGER DEFAULT 0,
                last_updated      TEXT
            )
        """)
        # Seed the single bank row if not present
        await db.execute(
            "INSERT OR IGNORE INTO casino_bank (id, balance) VALUES (1, 0)"
        )

        # casino_stats  –  per-user casino statistics
        await db.execute("""
            CREATE TABLE IF NOT EXISTS casino_stats (
                user_id        INTEGER PRIMARY KEY,
                games_played   INTEGER DEFAULT 0,
                games_won      INTEGER DEFAULT 0,
                total_wagered  INTEGER DEFAULT 0,
                total_won      INTEGER DEFAULT 0,
                total_lost     INTEGER DEFAULT 0,
                biggest_win    INTEGER DEFAULT 0,
                biggest_loss   INTEGER DEFAULT 0,
                jackpots       INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # casino_log  –  full transaction audit trail
        await db.execute("""
            CREATE TABLE IF NOT EXISTS casino_log (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                game           TEXT NOT NULL,
                bet            INTEGER NOT NULL,
                outcome        INTEGER NOT NULL,   -- +net won / -net lost (0 = push)
                balance_after  INTEGER NOT NULL,
                timestamp      TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # casino_bans  –  users banned from casino by admins
        await db.execute("""
            CREATE TABLE IF NOT EXISTS casino_bans (
                user_id    INTEGER PRIMARY KEY,
                banned_by  INTEGER,
                reason     TEXT,
                banned_at  TEXT
            )
        """)

        # casino_bet_limits  –  per-user custom bet caps set by admins
        await db.execute("""
            CREATE TABLE IF NOT EXISTS casino_bet_limits (
                user_id   INTEGER PRIMARY KEY,
                max_bet   INTEGER NOT NULL
            )
        """)

        await db.commit()
        logger.info("Casino database tables ready.")


# ─────────────────────────────────────────────────────────────────────────────
# User casino stats helpers
# ─────────────────────────────────────────────────────────────────────────────

async def ensure_casino_stats(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO casino_stats (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()


async def get_casino_stats(user_id: int) -> dict:
    await ensure_casino_stats(user_id)
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM casino_stats WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else {}


async def record_game(user_id: int, game: str, bet: int, outcome: int, balance_after: int):
    """
    Record a completed game.

    outcome > 0  = net coins won
    outcome < 0  = net coins lost
    outcome = 0  = push / refund
    """
    now = datetime.now(timezone.utc).isoformat()
    await ensure_casino_stats(user_id)

    won = outcome > 0
    lost = outcome < 0

    async with aiosqlite.connect(config.DB_PATH) as db:
        # Update rolling stats
        await db.execute("""
            UPDATE casino_stats SET
                games_played  = games_played + 1,
                games_won     = games_won + ?,
                total_wagered = total_wagered + ?,
                total_won     = total_won + ?,
                total_lost    = total_lost + ?,
                biggest_win   = MAX(biggest_win, ?),
                biggest_loss  = MAX(biggest_loss, ?)
            WHERE user_id = ?
        """, (
            1 if won else 0,
            bet,
            outcome if won else 0,
            abs(outcome) if lost else 0,
            outcome if won else 0,
            abs(outcome) if lost else 0,
            user_id,
        ))

        # Audit log
        await db.execute("""
            INSERT INTO casino_log (user_id, game, bet, outcome, balance_after, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, game, bet, outcome, balance_after, now))

        await db.commit()


async def increment_jackpots(user_id: int):
    await ensure_casino_stats(user_id)
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE casino_stats SET jackpots = jackpots + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Casino bank helpers
# ─────────────────────────────────────────────────────────────────────────────

async def get_bank_balance() -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT balance FROM casino_bank WHERE id = 1") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def add_to_bank(amount: int):
    """House edge / fees flow here."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            UPDATE casino_bank
            SET balance = balance + ?,
                total_collected = total_collected + ?,
                last_updated = ?
            WHERE id = 1
        """, (amount, amount, now))
        await db.commit()


async def pay_from_bank(amount: int) -> bool:
    """Admin cash-out or jackpot top-up. Returns False if insufficient funds."""
    bal = await get_bank_balance()
    if bal < amount:
        return False
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            UPDATE casino_bank
            SET balance = balance - ?,
                total_paid_out = total_paid_out + ?,
                last_updated = ?
            WHERE id = 1
        """, (amount, amount, now))
        await db.commit()
    return True


async def get_bank_stats() -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM casino_bank WHERE id = 1") as cur:
            row = await cur.fetchone()
            return dict(row) if row else {}


# ─────────────────────────────────────────────────────────────────────────────
# Bet validation helpers
# ─────────────────────────────────────────────────────────────────────────────

async def is_casino_banned(user_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM casino_bans WHERE user_id = ?", (user_id,)
        ) as cur:
            return (await cur.fetchone()) is not None


async def get_user_max_bet(user_id: int) -> int:
    """Return user's personal max bet cap, or the global default."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT max_bet FROM casino_bet_limits WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else config.CASINO["max_bet"]


async def ban_user(user_id: int, banned_by: int, reason: str = None):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO casino_bans (user_id, banned_by, reason, banned_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, banned_by, reason, now))
        await db.commit()


async def unban_user(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM casino_bans WHERE user_id = ?", (user_id,))
        await db.commit()


async def set_bet_limit(user_id: int, max_bet: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO casino_bet_limits (user_id, max_bet)
            VALUES (?, ?)
        """, (user_id, max_bet))
        await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Leaderboard helpers
# ─────────────────────────────────────────────────────────────────────────────

async def get_top_winners(limit: int = 10) -> list:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT cs.user_id, cs.total_won, cs.biggest_win, cs.games_won,
                   cs.games_played, cs.jackpots, u.username
            FROM casino_stats cs
            LEFT JOIN users u ON cs.user_id = u.user_id
            WHERE cs.games_played > 0
            ORDER BY cs.total_won DESC
            LIMIT ?
        """, (limit,)) as cur:
            return await cur.fetchall()


async def get_recent_log(limit: int = 20) -> list:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT cl.*, u.username
            FROM casino_log cl
            LEFT JOIN users u ON cl.user_id = u.user_id
            ORDER BY cl.id DESC
            LIMIT ?
        """, (limit,)) as cur:
            return await cur.fetchall()
