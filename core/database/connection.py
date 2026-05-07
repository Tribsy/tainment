"""
core/database/connection.py — shared aiosqlite connection setup.

PRAGMA settings live here so every domain's init() shares the same
connection-wide configuration. Call apply_pragmas() once at startup before
any per-domain init().
"""
import aiosqlite
import config


async def apply_pragmas():
    """Set persistent connection pragmas. Call once at startup."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")       # concurrent reads + faster writes
        await db.execute("PRAGMA synchronous = NORMAL")     # safe but faster than FULL
        await db.execute("PRAGMA cache_size = -8000")       # 8 MB page cache
        await db.execute("PRAGMA temp_store = MEMORY")      # temp tables in RAM
        await db.commit()
