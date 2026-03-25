"""
ledger/event_store.py — PostgreSQL-backed EventStore
=====================================================
COMPLETION CHECKLIST (implement in order):
  [ ] Phase 1, Day 1: append() + stream_version()
  [ ] Phase 1, Day 1: load_stream()
  [ ] Phase 1, Day 2: load_all()  (needed for projection daemon)
  [ ] Phase 1, Day 2: get_event() (needed for causation chain)
  [ ] Phase 4:        UpcasterRegistry.upcast() integration in load_stream/load_all
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import AsyncGenerator, AsyncIterator
from uuid import UUID
import asyncpg
from src.models.events import BaseEvent, StoredEvent
from src.upcasting.registry import event_registry
import src.upcasting.upcasters
class OptimisticConcurrencyError(Exception):
    """Raised when expected_version doesn't match current stream version."""
    def __init__(self, stream_id: str, expected: int, actual: int):
        self.stream_id = stream_id; self.expected = expected; self.actual = actual
        super().__init__(f"OCC on '{stream_id}': expected v{expected}, actual v{actual}")


class EventStore:
    """
    Append-only PostgreSQL event store. All agents and projections use this class.

    IMPLEMENT IN ORDER — see inline guides in each method:
      1. stream_version()   — simplest, needed immediately
      2. append()           — most critical; OCC correctness is the exam
      3. load_stream()      — needed for aggregate replay
      4. load_all()         — async generator, needed for projection daemon
      5. get_event()        — needed for causation chain audit
    """

    def __init__(self, db_url: str, upcaster_registry=None):
        self.db_url = db_url
        self.upcasters = upcaster_registry
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self.db_url, min_size=2, max_size=10)

    async def close(self) -> None:
        if self._pool: await self._pool.close()

    #Phase-1 Step-1: Updated stream_version() method that was given on the starter code
    async def stream_version(self, stream_id: str) -> int:
        """
        Returns current version, or -1 if stream doesn't exist.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT current_version FROM event_streams WHERE stream_id = $1",
                stream_id
            )
            return row["current_version"] if row else -1

    #Phase-1 Step-2: Updated the append() method that was given on the starter code
    # In src/event_store.py

# Replace the entire 'append' method with this one:

    async def append(
        self,
        stream_id: str,
        events: list[dict],
        expected_version: int,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> list[int]:
        
        async with self._pool.acquire() as conn:
            # Start a database transaction
            async with conn.transaction():
                # 1. Get the current version of the stream
                current_version_record = await conn.fetchrow(
                    "SELECT current_version FROM event_streams WHERE stream_id = $1 FOR UPDATE",
                    stream_id
                )
                
                # --- THIS IS THE CORE FIX ---
                # If the record is None, the stream doesn't exist yet. Its version is 0.
                current_version = current_version_record['current_version'] if current_version_record else 0

                # 2. Optimistic Concurrency Check
                if current_version != expected_version:
                    raise OptimisticConcurrencyError(stream_id, expected_version, current_version)

                # 3. Insert the new events
                new_version = current_version
                new_event_ids = []
                for event in events:
                    new_version += 1
                    event_id = await conn.fetchval(
                        """
                        INSERT INTO events (stream_id, stream_position, event_type, event_version, payload, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING event_id
                        """,
                        stream_id,
                        new_version,
                        event["event_type"],
                        event["event_version"],
                        json.dumps(event["payload"]),
                        json.dumps({"correlation_id": correlation_id, "causation_id": causation_id}),
                    )
                    new_event_ids.append(event_id)

                # 4. Update the stream's version (UPSERT)
                # This will create the stream record if it's the first time, or update it if it exists.
                await conn.execute(
                    """
                    INSERT INTO event_streams (stream_id, aggregate_type, current_version)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (stream_id) DO UPDATE SET current_version = $3
                    """,
                    stream_id,
                    stream_id.split('-')[0], # Extract aggregate type from stream_id
                    new_version
                )
                
                return new_event_ids


    #Phase-1 Step-3: Updated the load_stream() method that was given on the starter code
    async def load_stream(self, stream_id: str) -> list[StoredEvent]:
        """
        Loads all events for a given stream, upcasting them to the latest version.
        """
        async with self._pool.acquire() as conn:
            # --- THIS IS THE FIX ---
            # The full, correct SQL query is here.
            rows = await conn.fetch(
                """
                SELECT event_id, stream_id, stream_position, event_type,
                    event_version, payload, metadata, recorded_at, global_position
                FROM events 
                WHERE stream_id = $1
                ORDER BY stream_position ASC
                """,
                stream_id
            )
            # --- END OF FIX ---
            
            events = []
            for row in rows:
                payload_dict = json.loads(row["payload"]) if isinstance(row["payload"], str) else (row["payload"] or {})
                
                print(f"--- DEBUG: Processing Event ---")
                print(f"  - Event Type: {row['event_type']}")
                print(f"  - Original DB Version: {row['event_version']}")
                print(f"  - Original Payload: {payload_dict}")

                upcasted_payload = event_registry.upcast(row["event_type"], payload_dict)
                
                print(f"  - Upcasted Payload: {upcasted_payload}")

                # Determine the final version from the upcasted payload, falling back to the row's version
                final_version = upcasted_payload.get("event_version", row["event_version"])
                print(f"  - Final Version determined: {final_version}")
                
                event = StoredEvent(
                    event_id=row["event_id"],
                    stream_id=row["stream_id"],
                    stream_position=row["stream_position"],
                    event_type=row["event_type"],
                    event_version=final_version,
                    payload=upcasted_payload,
                    metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
                    recorded_at=row["recorded_at"],
                    global_position=row["global_position"],
                )
                events.append(event)
            return events

    #Phase-1 Step-4: Updated the load_all() method that was given on the starter code
    async def load_all(
        self,
        from_global_position: int = 0,
        event_types: list[str] | None = None,
        batch_size: int = 500,
    ) -> AsyncIterator[StoredEvent]:
        """
        Async generator yielding events in global_position order.
        """
        async with self._pool.acquire() as conn:
            pos = from_global_position
            while True:
                if event_types is None:
                    rows = await conn.fetch(
                        """
                        SELECT event_id, stream_id, stream_position, event_type,
                               event_version, payload, metadata, recorded_at,
                               global_position
                        FROM events 
                        WHERE global_position > $1
                        ORDER BY global_position ASC 
                        LIMIT $2
                        """,
                        pos, batch_size
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT event_id, stream_id, stream_position, event_type,
                               event_version, payload, metadata, recorded_at,
                               global_position
                        FROM events 
                        WHERE global_position > $1 AND event_type = ANY($2::text[])
                        ORDER BY global_position ASC 
                        LIMIT $3
                        """,
                        pos, event_types, batch_size
                    )
                if not rows:
                    break
                for row in rows:
                    event = StoredEvent(
                        event_id=row["event_id"],
                        stream_id=row["stream_id"],
                        stream_position=row["stream_position"],
                        event_type=row["event_type"],
                        event_version=row["event_version"],
                        payload=json.loads(row["payload"]) if isinstance(row["payload"], str) else (dict(row["payload"]) if row["payload"] is not None else {}),
                        metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (dict(row["metadata"]) if row["metadata"] is not None else {}),
                        recorded_at=row["recorded_at"],
                        global_position=row["global_position"],
                    )
                    if self.upcasters:
                        event = self.upcasters.upcast(event)
                    yield event
                if len(rows) < batch_size:
                    break
                pos = rows[-1]["global_position"]
        
    #Phase-1 Step-5.1: Updated the get_event() method that was given on the starter code
    async def get_event(self, event_id: UUID) -> StoredEvent | None:
        """
        Loads one event by UUID. Used for causation chain lookups.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT event_id, stream_id, stream_position, event_type,
                       event_version, payload, metadata, recorded_at
                FROM events 
                WHERE event_id = $1
                """,
                event_id
            )
            if not row:
                return None
            event = StoredEvent(
                event_id=row["event_id"],
                stream_id=row["stream_id"],
                stream_position=row["stream_position"],
                event_type=row["event_type"],
                event_version=row["event_version"],
                payload=json.loads(row["payload"]) if isinstance(row["payload"], str) else (dict(row["payload"]) if row["payload"] is not None else {}),
                metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (dict(row["metadata"]) if row["metadata"] is not None else {}),
                recorded_at=row["recorded_at"],
            )
            if self.upcasters:
                event = self.upcasters.upcast(event)
            return event

    #Phase-1 Step-5.2: Created the archive_stream() method that wasn't given on the starter code
    async def archive_stream(self, stream_id: str) -> None:
        """
        Marks a stream as archived (Phase 4+).
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE event_streams SET archived_at = NOW() WHERE stream_id = $1",
                stream_id
            )

    #Phase-1 Step-5.3: Created the get_stream_metadata() method that wasn't given on the starter code
    async def get_stream_metadata(self, stream_id: str) -> dict:
        """
        Returns metadata for a stream (used by projections and MCP).
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT stream_id, aggregate_type, current_version,
                       created_at, archived_at, metadata
                FROM event_streams 
                WHERE stream_id = $1
                """,
                stream_id
            )
            if not row:
                return {"current_version": -1}
            return {
                "stream_id": row["stream_id"],
                "aggregate_type": row["aggregate_type"],
                "current_version": row["current_version"],
                "created_at": row["created_at"],
                "archived_at": row["archived_at"],
                "metadata": dict(row["metadata"]),
            }

    async def load_aggregate(self, stream_id: str, aggregate_class):
        """Helper method to load an aggregate instance from its event stream."""
        aggregate = aggregate_class()
        
        # Set the stream_id FIRST, so the aggregate knows its own identity
        aggregate.stream_id = stream_id
        
        events_list = await self.load_stream(stream_id)
            
        # The apply_events method from BaseAggregate will loop, call apply(), and set the version.
        aggregate.apply_events(events_list)
        
        return aggregate
    
    async def append_to_stream(self, aggregate):
        """Helper method to save new events from an aggregate."""
        if not aggregate.has_new_events():
            return
            
        # --- THIS IS THE FIX ---
        # The expected version for the write operation is the aggregate's version
        # MINUS the number of new events it has.
        # For a new aggregate, version=3, new_events=3, so expected_version=0.
        # For an existing aggregate, version=6, new_events=2, so expected_version=4.
        expected_version = aggregate.version - len(aggregate.new_events)
        
        return await self.append(
            stream_id=aggregate.stream_id,
            events=[event.to_store_dict() for event in aggregate.new_events],
            expected_version=expected_version
        )

# ─────────────────────────────────────────────────────────────────────────────
# UPCASTER REGISTRY — Phase 4
# ─────────────────────────────────────────────────────────────────────────────

class UpcasterRegistry:
    """
    Transforms old event versions to current versions on load.
    Upcasters are PURE functions — they never write to the database.

    REGISTER AN UPCASTER:
        registry = UpcasterRegistry()

        @registry.upcaster("CreditAnalysisCompleted", from_version=1, to_version=2)
        def upcast_credit_v1_v2(payload: dict) -> dict:
            # v2 adds model_versions dict
            payload.setdefault("model_versions", {})
            return payload

    REQUIRED FOR PHASE 4:
        - CreditAnalysisCompleted  v1 → v2  (adds model_versions: dict)
        - DecisionGenerated        v1 → v2  (adds model_versions: dict)

    IMMUTABILITY TEST (required artifact):
        registry.assert_upcaster_does_not_write_to_db(store, event)
        # Loads the event, upcasts it, re-loads it, confirms DB row unchanged.
    """

    def __init__(self):
        self._upcasters: dict[str, dict[int, callable]] = {}

    def upcaster(self, event_type: str, from_version: int, to_version: int):
        def decorator(fn):
            self._upcasters.setdefault(event_type, {})[from_version] = fn
            return fn
        return decorator

    def upcast(self, event: dict) -> dict:
        """Apply chain of upcasters until latest version reached."""
        et = event["event_type"]
        v = event.get("event_version", 1)
        chain = self._upcasters.get(et, {})
        while v in chain:
            event["payload"] = chain[v](dict(event["payload"]))
            v += 1
            event["event_version"] = v
        return event


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY EVENT STORE — for tests only
# ─────────────────────────────────────────────────────────────────────────────

class InMemoryEventStore:
    """
    In-memory event store for unit tests. No database required.
    Identical interface to EventStore — swap transparently in conftest.py.

    Your Phase 1 tests use this. Once EventStore is implemented and a test
    database is available, you can run all tests against the real store too.
    """

    def __init__(self, upcaster_registry=None):
        self.upcasters = upcaster_registry
        self._streams: dict[str, list[dict]] = {}   # stream_id → [event_dict, ...]
        self._global: list[dict] = []               # all events in global order

    async def stream_version(self, stream_id: str) -> int:
        events = self._streams.get(stream_id, [])
        return len(events) - 1  # -1 if empty, 0-based index otherwise

    async def append(
        self,
        stream_id: str,
        events: list[dict],
        expected_version: int,
        causation_id: str | None = None,
        metadata: dict | None = None,
    ) -> list[int]:
        current = await self.stream_version(stream_id)
        if current != expected_version:
            raise OptimisticConcurrencyError(stream_id, expected_version, current)

        self._streams.setdefault(stream_id, [])
        positions = []
        for i, event in enumerate(events):
            pos = expected_version + 1 + i
            stored = {
                "event_id": str(__import__("uuid").uuid4()),
                "stream_id": stream_id,
                "stream_position": pos,
                "global_position": len(self._global),
                "event_type": event["event_type"],
                "event_version": event.get("event_version", 1),
                "payload": dict(event.get("payload", {})),
                "metadata": {**(metadata or {}), **({"causation_id": causation_id} if causation_id else {})},
                "recorded_at": __import__("datetime").datetime.utcnow(),
            }
            self._streams[stream_id].append(stored)
            self._global.append(stored)
            positions.append(pos)
        return positions

    async def load_stream(
        self,
        stream_id: str,
        from_position: int = 0,
        to_position: int | None = None,
    ) -> list[dict]:
        events = self._streams.get(stream_id, [])
        result = [e for e in events if e["stream_position"] >= from_position]
        if to_position is not None:
            result = [e for e in result if e["stream_position"] <= to_position]
        if self.upcasters:
            result = [self.upcasters.upcast(dict(e)) for e in result]
        return result

    async def load_all(
        self, from_position: int = 0, batch_size: int = 500
    ):
        for event in self._global:
            if event["global_position"] >= from_position:
                yield dict(event)

    async def get_event(self, event_id) -> dict | None:
        for event in self._global:
            if event["event_id"] == str(event_id):
                return dict(event)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY EVENT STORE — for Phase 1 tests only
# Identical interface to EventStore. Drop-in for tests; never use in production.
# ─────────────────────────────────────────────────────────────────────────────

import asyncio as _asyncio
from collections import defaultdict as _defaultdict
from datetime import datetime as _datetime
from uuid import uuid4 as _uuid4

class InMemoryEventStore:
    """
    Thread-safe (asyncio-safe) in-memory event store.
    Used exclusively in Phase 1 tests and conftest fixtures.
    Same interface as EventStore — swap one for the other with no code changes.
    """

    def __init__(self):
        # stream_id -> list of event dicts
        self._streams: dict[str, list[dict]] = _defaultdict(list)
        # stream_id -> current version (position of last event, -1 if empty)
        self._versions: dict[str, int] = {}
        # global append log (ordered by insertion)
        self._global: list[dict] = []
        # projection checkpoints
        self._checkpoints: dict[str, int] = {}
        # asyncio lock per stream for OCC
        self._locks: dict[str, _asyncio.Lock] = _defaultdict(_asyncio.Lock)

    async def stream_version(self, stream_id: str) -> int:
        return self._versions.get(stream_id, -1)

    async def append(
        self,
        stream_id: str,
        events: list[dict],
        expected_version: int,
        causation_id: str | None = None,
        metadata: dict | None = None,
    ) -> list[int]:
        async with self._locks[stream_id]:
            current = self._versions.get(stream_id, -1)
            if current != expected_version:
                raise OptimisticConcurrencyError(stream_id, expected_version, current)

            positions = []
            meta = {**(metadata or {})}
            if causation_id:
                meta["causation_id"] = causation_id

            for i, event in enumerate(events):
                pos = current + 1 + i
                stored = {
                    "event_id": str(_uuid4()),
                    "stream_id": stream_id,
                    "stream_position": pos,
                    "global_position": len(self._global),
                    "event_type": event["event_type"],
                    "event_version": event.get("event_version", 1),
                    "payload": dict(event.get("payload", {})),
                    "metadata": meta,
                    "recorded_at": _datetime.utcnow().isoformat(),
                }
                self._streams[stream_id].append(stored)
                self._global.append(stored)
                positions.append(pos)

            self._versions[stream_id] = current + len(events)
            return positions

    async def load_stream(
        self,
        stream_id: str,
        from_position: int = 0,
        to_position: int | None = None,
    ) -> list[dict]:
        events = [
            e for e in self._streams.get(stream_id, [])
            if e["stream_position"] >= from_position
            and (to_position is None or e["stream_position"] <= to_position)
        ]
        return sorted(events, key=lambda e: e["stream_position"])

    async def load_all(self, from_position: int = 0, batch_size: int = 500):
        for e in self._global:
            if e["global_position"] >= from_position:
                yield e

    async def get_event(self, event_id: str) -> dict | None:
        for e in self._global:
            if e["event_id"] == event_id:
                return e
        return None

    async def save_checkpoint(self, projection_name: str, position: int) -> None:
        self._checkpoints[projection_name] = position

    async def load_checkpoint(self, projection_name: str) -> int:
        return self._checkpoints.get(projection_name, 0)
