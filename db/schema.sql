-- ============================================================
-- customer_journey_forensics.db  —  Full Schema
-- ============================================================

-- ------------------------------------------------------------
-- 1. CUSTOMERS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    customer_id                TEXT PRIMARY KEY,
    customer_name              TEXT NOT NULL,
    industry                   TEXT NOT NULL,
    loyalty_tier               TEXT,
    relationship_length_years  INTEGER,
    plan_type                  TEXT,
    account_number             TEXT,
    member_id                  TEXT,
    policy_number              TEXT
);

CREATE INDEX IF NOT EXISTS idx_customers_industry ON customers(industry);

-- ------------------------------------------------------------
-- 2. AGENTS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agents (
    agent_id    TEXT PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    team_id     TEXT,
    team_name   TEXT,
    agent_type  TEXT NOT NULL CHECK (agent_type IN ('Human', 'Bot', 'System'))
);

-- ------------------------------------------------------------
-- 3. CHANNELS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS channels (
    channel_id    TEXT PRIMARY KEY,
    channel_name  TEXT NOT NULL,
    media_type    TEXT NOT NULL
);

-- ------------------------------------------------------------
-- 4. JOURNEY_SESSIONS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS journey_sessions (
    master_contact_id   TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(customer_id),
    tenant_id           TEXT,
    industry            TEXT NOT NULL,
    scenario_title      TEXT,
    case_reference_id   TEXT,
    case_type           TEXT,
    first_contact_time  DATETIME,
    last_contact_time   DATETIME,
    total_interactions  INTEGER DEFAULT 0,
    risk_score          REAL,
    risk_label          TEXT,
    session_status      TEXT NOT NULL DEFAULT 'Open'
                            CHECK (session_status IN ('Open','Resolved','Escalated')),
    root_cause          TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_customer    ON journey_sessions(customer_id);
CREATE INDEX IF NOT EXISTS idx_sessions_industry    ON journey_sessions(industry);
CREATE INDEX IF NOT EXISTS idx_sessions_status      ON journey_sessions(session_status);
CREATE INDEX IF NOT EXISTS idx_sessions_risk_score  ON journey_sessions(risk_score);

-- ------------------------------------------------------------
-- 5. INTERACTIONS  (central fact table)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interactions (
    contact_id            TEXT PRIMARY KEY,
    master_contact_id     TEXT NOT NULL REFERENCES journey_sessions(master_contact_id),
    tenant_id             TEXT,
    start_time            DATETIME NOT NULL,
    end_time              DATETIME,
    ingestion_time        DATETIME,
    media_type            TEXT NOT NULL,
    direction             TEXT NOT NULL CHECK (direction IN ('INBOUND','OUTBOUND')),
    channel_id            TEXT REFERENCES channels(channel_id),
    skill_id              TEXT,
    skill_name            TEXT,
    agent_id              TEXT REFERENCES agents(agent_id),
    agent_disposition     TEXT,
    duration_seconds      INTEGER,
    overall_sentiment     TEXT,
    csat                  INTEGER CHECK (csat BETWEEN 1 AND 5),
    transfer_flag         INTEGER NOT NULL DEFAULT 0 CHECK (transfer_flag IN (0,1)),
    escalation_flag       INTEGER NOT NULL DEFAULT 0 CHECK (escalation_flag IN (0,1)),
    interaction_sequence  INTEGER NOT NULL,
    recording_id          TEXT,
    recording_status      TEXT,
    redaction_status      TEXT,
    ani                   TEXT,
    dnis                  TEXT,
    from_address          TEXT,
    to_address            TEXT,
    business_data         TEXT,
    transcript            TEXT,
    outcome               TEXT
);

CREATE INDEX IF NOT EXISTS idx_interactions_session    ON interactions(master_contact_id);
CREATE INDEX IF NOT EXISTS idx_interactions_agent      ON interactions(agent_id);
CREATE INDEX IF NOT EXISTS idx_interactions_channel    ON interactions(channel_id);
CREATE INDEX IF NOT EXISTS idx_interactions_start_time ON interactions(start_time);
CREATE INDEX IF NOT EXISTS idx_interactions_escalation ON interactions(escalation_flag);
CREATE INDEX IF NOT EXISTS idx_interactions_sentiment  ON interactions(overall_sentiment);
CREATE INDEX IF NOT EXISTS idx_interactions_sequence   ON interactions(master_contact_id, interaction_sequence);

-- ------------------------------------------------------------
-- 6. FAILURE_PATTERNS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS failure_patterns (
    pattern_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    master_contact_id   TEXT NOT NULL REFERENCES journey_sessions(master_contact_id),
    severity            TEXT NOT NULL CHECK (severity IN ('CRITICAL','WARNING')),
    pattern_type        TEXT NOT NULL,
    pattern_description TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_patterns_session   ON failure_patterns(master_contact_id);
CREATE INDEX IF NOT EXISTS idx_patterns_type      ON failure_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_severity  ON failure_patterns(severity);

-- ------------------------------------------------------------
-- 7. RECOMMENDED_ACTIONS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recommended_actions (
    action_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    master_contact_id   TEXT NOT NULL REFERENCES journey_sessions(master_contact_id),
    priority            TEXT NOT NULL CHECK (priority IN ('Critical','High','Medium','Low')),
    action_text         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_actions_session  ON recommended_actions(master_contact_id);
CREATE INDEX IF NOT EXISTS idx_actions_priority ON recommended_actions(priority);
