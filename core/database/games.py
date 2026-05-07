"""
core/database/games.py — game high scores and story progress.

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging


logger = logging.getLogger("tainment.database.games")


async def init():
    """Create tables and run migrations for the games domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS story_progress (
                user_id INTEGER,
                story_key TEXT,
                part INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, story_key),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────

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

