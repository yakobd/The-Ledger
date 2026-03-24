# scripts/run_daemon.py

import asyncio
import os

from src.event_store import EventStore
from src.projections.daemon import ProjectionDaemon
from dotenv import load_dotenv

async def main():
    """
    Initializes and runs the ProjectionDaemon forever.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("❌ FATAL: DATABASE_URL environment variable is not set. Please check your .env file.")

    event_store = EventStore(db_url)
    await event_store.connect()

    daemon = ProjectionDaemon(event_store)
    
    try:
        await daemon.run_forever()
    finally:
        await event_store.close()


if __name__ == "__main__":
    # Ensure you have your .env file with DATABASE_URL or have it set in your environment
    
    load_dotenv()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Daemon stopped manually.")

