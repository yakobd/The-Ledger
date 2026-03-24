import asyncio
from src.projections.daemon import ProjectionDaemon

async def main():
    daemon = ProjectionDaemon(
        db_url="postgresql://postgres:apex@localhost/apex_ledger",
        projection_name="test_projection"
    )
    try:
        await daemon.connect()
        print("✅ ProjectionDaemon connected successfully")
        # Run for 3 seconds then stop
        await asyncio.sleep(3)
    finally:
        await daemon.event_store.close()

if __name__ == "__main__":
    asyncio.run(main())