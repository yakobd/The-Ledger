# DESIGN.md — The Ledger (Phase 1)

**TRP1 Week 5 – The Ledger**  
**Author**: Yakob Dereje  
**Date**: March 2026  

## Database Schema Justification

All tables and columns exactly match the challenge document. Every column is justified below.

### events table
- `event_id` (UUID PK): Unique identifier for audit and causation chains.
- `stream_id` (TEXT): Groups events by aggregate (loan-*, agent-*, etc.).
- `stream_position` (BIGINT): Version within the stream for OCC.
- `global_position` (BIGINT GENERATED): Global order for projection daemon replay.
- `event_type` (TEXT): Type of event (ApplicationSubmitted, AgentNodeExecuted, etc.).
- `event_version` (SMALLINT): For upcasting/schema evolution.
- `payload` (JSONB): Immutable business data.
- `metadata` (JSONB): Causation_id, correlation_id, recorded_at details.
- `recorded_at` (TIMESTAMPTZ): Audit timestamp.
- Indexes: All required for performance and OCC.

### event_streams table
- `stream_id` (PK): Unique per aggregate.
- `aggregate_type`: For quick filtering.
- `current_version`: For OCC checks.
- `created_at` / `archived_at`: Lifecycle management.
- `metadata`: Future extensions.

### projection_checkpoints table
- `projection_name` (PK): Name of projection.
- `last_position`: Checkpoint for async daemon.
- `updated_at`: Last update time.

### outbox table
- `id` (UUID PK): Unique outbox entry.
- `event_id` (FK): Links to events.
- `destination`: 'projection', 'mcp', etc.
- `payload`: Copy of event for reliable delivery.
- `created_at` / `published_at` / `attempts`: Outbox pattern reliability.

No unnecessary columns. Schema is complete and production-ready.

Prepared for Phase 1 submission.