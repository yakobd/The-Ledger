# scripts/run_projections_once.py

# --- Path Setup ---
import sys, os, asyncio
from dotenv import load_dotenv

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
# ---

from src.event_store import EventStore
from src.projections.daemon import ProjectionDaemon

async def main():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: raise ValueError("DATABASE_URL not set")
    
    event_store = EventStore(db_url)
    await event_store.connect()
    
    print("--- Running Projections ONCE ---")
    
    # 1. Instantiate the daemon
    daemon = ProjectionDaemon(event_store)
    
    # 2. Manually call the registration
    await daemon.register_projectors()
    print(f"Registered Projectors: {daemon._projector_map.keys()}")
    
    # 3. Acquire a connection and manually call the processing logic
    try:
        async with event_store._pool.acquire() as conn:
            print("  -> Database connection acquired.")
            # We skip the lock for this single-run test
            await daemon._process_batch(conn)
        print("--- Projection run finished ---")
    
    except Exception as e:
        print(f"--- An error occurred ---")
        print(e)
    
    finally:
        await event_store.close()
        print("--- Database connection closed ---")


if __name__ == "__main__":
    # Run the datagen first to ensure there is data
    from scripts.init_db import main as init_db
    print("Initializing clean database...")
    asyncio.run(init_db())

    from datagen.generate_all import main as generate_all
    print("\nGenerating data...")
    generate_all() # This is a synchronous function call
    
    print("\nRunning projection test...")
    asyncio.run(main())
