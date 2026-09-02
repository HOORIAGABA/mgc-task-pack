-- MGC Leads CRM — minimal schema
-- Dialect: PostgreSQL (works on SQLite 3.25+ with minor adjustments)

CREATE TABLE leads (
    lead_id             TEXT        PRIMARY KEY,       -- e.g. 'MGC-104067', unique per CRM row
    created_at          TIMESTAMP   NOT NULL,
    source              TEXT        NOT NULL,          -- e.g. 'Facebook Ads', 'Walk-in'
    city                TEXT,
    area                TEXT,
    property_type       TEXT,                          -- e.g. 'Apartment', 'Plot'
    budget_pkr_lac      NUMERIC,                       -- budget in PKR lakhs
    bedrooms            SMALLINT,
    first_response_minutes  NUMERIC,                   -- minutes to first agent contact
    calls_made          SMALLINT       DEFAULT 0,
    total_call_seconds  NUMERIC        DEFAULT 0,
    whatsapp_replies    SMALLINT       DEFAULT 0,
    site_visits         SMALLINT       DEFAULT 0,
    agent_experience_years NUMERIC,
    is_overseas         BOOLEAN        DEFAULT FALSE,
    referred_by_existing_client BOOLEAN DEFAULT FALSE,
    has_financing_approved BOOLEAN    DEFAULT FALSE,
    token_amount_received_pkr NUMERIC  DEFAULT 0,
    crm_record_hash     TEXT        NOT NULL,          -- dedup key: same person entered twice
    converted           BOOLEAN        DEFAULT FALSE
);

-- Prevent duplicate leads at the schema level:
-- crm_record_hash uniquely identifies a person. Two rows with the same hash
-- means the same lead was entered by different agents. A UNIQUE constraint
-- makes the database reject the second insert, forcing the agent to search
-- for the existing record instead of creating a new one.
--
-- In production you'd also add an INSERT trigger or application-level upsert
-- that matches on (phone or CNIC) and merges rather than rejects, but the
-- UNIQUE constraint is the hard backstop.
CREATE UNIQUE INDEX idx_leads_crm_hash ON leads (crm_record_hash);

-- Useful indexes for the queries below
CREATE INDEX idx_leads_source ON leads (source);
CREATE INDEX idx_leads_converted ON leads (converted);
