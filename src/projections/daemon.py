# src/projections/daemon.py

import asyncio
import logging
from typing import Type

import asyncpg

from src.event_store import EventStore
from src.models.events import StoredEvent, BaseEvent, event_registry
from src.projections.base import BaseProjector
from .loan_summary_projector import LoanSummaryProjector

# --- TODO: Import your actual projector classes here ---
# from .loan_summary_projector import LoanSummaryProjector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECTION_LOCK_ID = 1  # A unique integer for the advisory lock
CHECKPOINT_NAME = "projection_daemon"

class ProjectionDaemon:
    """
    A background worker that runs projections to build and update read models.
    It uses a PostgreSQL advisory lock to ensure only one instance is running.
    """

    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        # This dictionary maps an event type name to a list of projector classes
        self._projector_map: dict[str, list[Type[BaseProjector]]] = {}

    async def register_projectors(self):
        """
        Initializes and maps all projectors to the events they handle.
        """
        # TODO: Add your projector classes to this list
        projector_classes = [
            LoanSummaryProjector,
        ]
        
        for proj_class in projector_classes:
            # We instantiate it here, but we'll re-instantiate with a connection later
            temp_instance = proj_class(conn=None) 
            for event_type in temp_instance.event_types:
                event_name = event_type.__name__
                if event_name not in self._projector_map:
                    self._projector_map[event_name] = []
                self._projector_map[event_name].append(proj_class)
        logger.info(f"Registered projectors: {self._projector_map}")


    async def run_forever(self, poll_interval: int = 2):
        """Main loop to acquire lock and process events."""
        await self.register_projectors()
        logger.info("Starting projection daemon...")
        while True:
            try:
                async with self.event_store._pool.acquire() as conn:
                    # This is our chosen leader election strategy
                    is_leader = await conn.fetchval("SELECT pg_try_advisory_lock($1)", PROJECTION_LOCK_ID)

                    if is_leader:
                        logger.debug("Acquired projection lock. Running as leader.")
                        try:
                            await self._process_batch(conn)
                        finally:
                            # Ensure we release the lock
                            await conn.execute("SELECT pg_advisory_unlock($1)", PROJECTION_LOCK_ID)
                    else:
                        logger.debug("Could not acquire projection lock. Another instance is leader.")
                
                await asyncio.sleep(poll_interval)

            except (asyncio.CancelledError, KeyboardInterrupt):
                logger.info("Projection daemon shutting down.")
                break
            except Exception:
                logger.exception("Error in projection daemon main loop. Retrying...")
                await asyncio.sleep(poll_interval * 2) # Backoff on error

    # async def _process_batch(self, conn: asyncpg.Connection):
    #     """The core logic of the daemon when it is the leader."""
    #     last_processed_position = await self._get_last_checkpoint(conn)
        
    #     # 1. Fetch the next batch of events from the main event store
    #     # events = [event async for event in self.event_store.load_all(after_global_position=last_processed_position, batch_size=100)]
    #     events = [event async for event in self.event_store.load_all(from_global_position=last_processed_position, batch_size=100)]

    #     if not events:
    #         logger.debug("No new events to project.")
    #         return

    #     logger.info(f"Projecting {len(events)} new events...")

    #     # 2. Process events one by one
    #     for stored_event in events:
    #         projector_classes = self._projector_map.get(stored_event.type, [])
    #         if not projector_classes:
    #             continue

    #         # Upcast the event payload if necessary before handling
    #         event_payload = event_registry.upcast(stored_event.type, stored_event.payload)
    #         event_model = event_registry.get_event_class(stored_event.type)(**event_payload)

    #         for proj_class in projector_classes:
    #             # Use a transaction for each event projection for atomicity
    #             async with conn.transaction():
    #                 projector_instance = proj_class(conn)
    #                 await projector_instance.handle(event_model)
        
    #     # 3. Update the checkpoint to the position of the last processed event
    #     latest_position = events[-1].global_position
    #     await self._update_checkpoint(conn, latest_position)
    #     logger.info(f"Projection checkpoint updated to global_position={latest_position}")
    # In src/projections/daemon.py, replace the whole _process_batch method:

    async def _process_batch(self, conn: asyncpg.Connection):
        """The core logic of the daemon when it is the leader."""
        last_processed_position = await self._get_last_checkpoint(conn)
        
        # This call is now working!
        events = [event async for event in self.event_store.load_all(from_global_position=last_processed_position, batch_size=100)]

        if not events:
            logger.debug("No new events to project.")
            return

        logger.info(f"Projecting {len(events)} new events...")

        for stored_event in events:
            # --- THE FIX IS HERE ---
            projector_classes = self._projector_map.get(stored_event.event_type, [])
            if not projector_classes:
                continue

            # --- AND HERE ---
            event_payload = event_registry.upcast(stored_event.event_type, stored_event.payload)
            # --- AND HERE ---
            event_model = event_registry.get_event_class(stored_event.event_type)(**event_payload)

            for proj_class in projector_classes:
                async with conn.transaction():
                    projector_instance = proj_class(conn)
                    await projector_instance.handle(event_model)
        
        latest_position = events[-1].global_position
        await self._update_checkpoint(conn, latest_position)
        logger.info(f"Projection checkpoint updated to global_position={latest_position}")



    async def _get_last_checkpoint(self, conn: asyncpg.Connection) -> int:
        """
        Retrieves the global_position of the last successfully processed event.
        """
        # The projection_checkpoints table needs to be created via schema
        position = await conn.fetchval(
            "SELECT last_position FROM projection_checkpoints WHERE projection_name = $1",
            CHECKPOINT_NAME
        )
        return position if position is not None else 0

    async def _update_checkpoint(self, conn: asyncpg.Connection, position: int):
        """
        Updates the checkpoint for the daemon atomically.
        """
        # This is an "UPSERT" operation
        await conn.execute(
            """
            INSERT INTO projection_checkpoints (projection_name, last_position)
            VALUES ($1, $2)
            ON CONFLICT (projection_name) DO UPDATE
            SET last_position = $2
            """,
            CHECKPOINT_NAME,
            position,
        )

