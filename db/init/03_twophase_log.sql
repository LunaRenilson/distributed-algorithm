-- Log persistente do Two-Phase Commit (2PC) e eventos ordenados por Lamport

CREATE TABLE IF NOT EXISTS two_phase_transactions (
    tx_id VARCHAR(64) PRIMARY KEY,
    coordinator_id VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL, -- PREPARING, PREPARED, COMMITTED, ABORTED
    payload JSONB NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS two_phase_participant_log (
    id BIGSERIAL PRIMARY KEY,
    tx_id VARCHAR(64) NOT NULL,
    node_id VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tx_node UNIQUE (tx_id, node_id)
);

CREATE TABLE IF NOT EXISTS distributed_ordered_events (
    id BIGSERIAL PRIMARY KEY,
    event_name VARCHAR(128) NOT NULL,
    lamport_clock INT NOT NULL,
    node_id VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dist_events_order 
    ON distributed_ordered_events (lamport_clock ASC, node_id ASC);
