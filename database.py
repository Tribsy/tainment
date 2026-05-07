"""
database.py — shim. Real code lives in core/database/<domain>.py.

Phase 1.5: this file used to be 1053 lines holding 14 tables and 67 functions.
It now re-exports the public API from the core.database package so existing
call sites (`import database as db`, `from database import init_db`) keep
working without modification.

Cogs migrated in Phase 3+ should import directly from core.database (or its
submodules) for clearer dependency tracking. This shim disappears once nothing
imports `database` directly.
"""
from core.database import *           # noqa: F401,F403  (re-export every public function)
from core.database import init_db     # noqa: F401      (explicit for clarity / linters)
