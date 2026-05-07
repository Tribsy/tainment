"""
core/database — split from monolithic database.py in Phase 1.5.

`init_db()` runs every domain's init() in dependency order (users first
because every other table FK-references it). Existing call sites at the root
go through database.py (a shim that re-exports this package).
"""
import logging

from .connection import apply_pragmas

# Domain modules — order matters: users first, the rest are independent.
from . import users
from . import subscriptions
from . import economy
from . import games
from . import levels
from . import giveaways
from . import polls
from . import reminders
from . import fishing
from . import messages
from . import spotify

# Re-export every public function so `from core.database import *` (used by
# the database.py shim) gets the full original API back.
from .users import *           # noqa: F401,F403
from .subscriptions import *   # noqa: F401,F403
from .economy import *         # noqa: F401,F403
from .games import *           # noqa: F401,F403
from .levels import *          # noqa: F401,F403
from .giveaways import *       # noqa: F401,F403
from .polls import *           # noqa: F401,F403
from .reminders import *       # noqa: F401,F403
from .fishing import *         # noqa: F401,F403
from .messages import *        # noqa: F401,F403
from .spotify import *         # noqa: F401,F403

logger = logging.getLogger("tainment.database")


async def init_db():
    """Initialize all DB tables and run migrations."""
    await apply_pragmas()
    await users.init()
    await subscriptions.init()
    await economy.init()
    await games.init()
    await levels.init()
    await giveaways.init()
    await polls.init()
    await reminders.init()
    await fishing.init()
    await messages.init()
    await spotify.init()
    logger.info("Database initialized successfully.")
