CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    venue VARCHAR(255),
    total_tickets INT NOT NULL CHECK (total_tickets > 0),
    tickets_remaining INT NOT NULL CHECK (tickets_remaining >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT events_remaining_lte_total CHECK (tickets_remaining <= total_tickets)
);

CREATE TABLE ticket_purchase_events (
    id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users (id),
    event_id INT NOT NULL REFERENCES events (id),
    quantity INT NOT NULL CHECK (quantity > 0),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ticket_purchase_events_event_created
    ON ticket_purchase_events (event_id, created_at);
