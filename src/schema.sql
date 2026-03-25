-- src/schema.sql
CREATE TABLE events (
  event_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stream_id        TEXT NOT NULL,
  stream_position  BIGINT NOT NULL,
  global_position  BIGINT GENERATED ALWAYS AS IDENTITY,
  event_type       TEXT NOT NULL,
  event_version    SMALLINT NOT NULL DEFAULT 1,
  payload          JSONB NOT NULL,
  metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
  recorded_at      TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT uq_stream_position UNIQUE (stream_id, stream_position)
);

CREATE INDEX idx_events_stream_id ON events (stream_id, stream_position);
CREATE INDEX idx_events_global_pos ON events (global_position);
CREATE INDEX idx_events_type ON events (event_type);
CREATE INDEX idx_events_recorded ON events (recorded_at);

CREATE TABLE event_streams (
  stream_id        TEXT PRIMARY KEY,
  aggregate_type   TEXT NOT NULL,
  current_version  BIGINT NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  archived_at      TIMESTAMPTZ,
  metadata         JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE projection_checkpoints (
  projection_name  TEXT PRIMARY KEY,
  last_position    BIGINT NOT NULL DEFAULT 0,
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE outbox (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id         UUID NOT NULL REFERENCES events(event_id),
  destination      TEXT NOT NULL,
  payload          JSONB NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  published_at     TIMESTAMPTZ,
  attempts         SMALLINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS projection_checkpoints (
    name VARCHAR(255) PRIMARY KEY,
    last_position BIGINT NOT NULL
);

-- Read Model for Loan Summaries
CREATE TABLE IF NOT EXISTS loan_summaries (
    application_id VARCHAR(255) PRIMARY KEY,
    applicant_name VARCHAR(255),
    status VARCHAR(50) NOT NULL,
    decision_reason TEXT,
    last_updated_at TIMESTAMPTZ NOT NULL
);

-- Read Model for Agent Performance
CREATE TABLE IF NOT EXISTS agent_performance_ledger (
    agent_id VARCHAR(255) PRIMARY KEY,
    model_version VARCHAR(255),
    analyses_completed INT NOT NULL DEFAULT 0,
    decisions_generated INT NOT NULL DEFAULT 0,
    avg_confidence_score FLOAT NOT NULL DEFAULT 0.0,
    avg_duration_ms BIGINT NOT NULL DEFAULT 0,
    approve_rate FLOAT NOT NULL DEFAULT 0.0,
    decline_rate FLOAT NOT NULL DEFAULT 0.0,
    refer_rate FLOAT NOT NULL DEFAULT 0.0,
    human_override_rate FLOAT NOT NULL DEFAULT 0.0,
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ
);


-- Read Model for Compliance Audit View (Temporal)
CREATE TABLE IF NOT EXISTS compliance_audit_view (
    id SERIAL PRIMARY KEY,
    application_id VARCHAR(255) NOT NULL,
    version INT NOT NULL,
    overall_verdict VARCHAR(50) NOT NULL,
    has_hard_block BOOLEAN NOT NULL,
    rules_passed INT NOT NULL,
    rules_failed INT NOT NULL,
    failed_rules_details JSONB, -- Store details of failed rules as JSON
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE(application_id, version)
);
CREATE INDEX idx_compliance_audit_app_id ON compliance_audit_view (application_id);
