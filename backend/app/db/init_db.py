"""
Database Initialization Utility
Creates tables and verifies connection and PRAGMA settings.
"""

import logging
from sqlalchemy import text
from backend.app.db.session import engine
from backend.app.db.models import Base

logger = logging.getLogger(__name__)


async def init_db() -> bool:
    """Initializes tables in the SQLite database and verifies WAL mode."""
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        
        # Verify WAL mode
        result = await conn.execute(text("PRAGMA journal_mode;"))
        mode = result.scalar()
        logger.info(f"Database initialized successfully. Journal mode: {mode}")

    return True


if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())

