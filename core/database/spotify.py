"""
core/database/spotify.py — linked Spotify accounts and API response cache.

Phase 1.5: extracted from monolithic database.py. Functions are moved verbatim
to keep diffs auditable; signatures and bodies are unchanged.
"""
import aiosqlite
import config
import logging


logger = logging.getLogger("tainment.database.spotify")


async def init():
    """Create tables and run migrations for the spotify domain."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS spotify_accounts (
                user_id       INTEGER PRIMARY KEY,
                access_token  TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at    INTEGER NOT NULL,
                scopes        TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS music_cache (
                cache_key  TEXT PRIMARY KEY,
                data_json  TEXT NOT NULL,
                fetched_at INTEGER NOT NULL,
                ttl_secs   INTEGER NOT NULL
            )
        """)
        await db.commit()


# ─── Functions (verbatim from database.py) ──────────────────────────────────


async def save_spotify_account(user_id: int, access_token: str, refresh_token: str, expires_at: int, scopes: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO spotify_accounts (user_id, access_token, refresh_token, expires_at, scopes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at,
                scopes = excluded.scopes
        """, (user_id, access_token, refresh_token, expires_at, scopes))
        await db.commit()


async def get_spotify_account(user_id: int) -> dict | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM spotify_accounts WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def delete_spotify_account(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM spotify_accounts WHERE user_id = ?", (user_id,))
        await db.commit()


# -- Music cache helpers --

async def get_music_cache(cache_key: str) -> dict | None:
    """Return cached entry if present and not expired, else None."""
    import time
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT data_json, fetched_at, ttl_secs FROM music_cache WHERE cache_key = ?",
            (cache_key,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    if time.time() > row['fetched_at'] + row['ttl_secs']:
        return None  # expired
    return {'data_json': row['data_json']}


async def set_music_cache(cache_key: str, data_json: str, ttl_secs: int):
    import time
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO music_cache (cache_key, data_json, fetched_at, ttl_secs)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                data_json = excluded.data_json,
                fetched_at = excluded.fetched_at,
                ttl_secs = excluded.ttl_secs
        """, (cache_key, data_json, int(time.time()), ttl_secs))
        await db.commit()
