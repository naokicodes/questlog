CREATE TABLE IF NOT EXISTS devices (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('laptop', 'phone')),
    token_hash    TEXT UNIQUE NOT NULL,
    created_at    TEXT NOT NULL,
    last_seen_at  TEXT
);

CREATE TABLE IF NOT EXISTS skills (
    id              INTEGER PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    laptop_tracked  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS journal_entries (
    id          INTEGER PRIMARY KEY,
    day         TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    body_md     TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attachments (
    id             INTEGER PRIMARY KEY,
    entry_id       INTEGER REFERENCES journal_entries(id),
    path           TEXT NOT NULL,
    mime           TEXT NOT NULL,
    sha256         TEXT NOT NULL,
    original_name  TEXT,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quest_templates (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    skill_id   INTEGER REFERENCES skills(id),
    verify     TEXT NOT NULL CHECK (verify IN ('auto', 'manual', 'photo')),
    rule_json  TEXT,
    required   INTEGER NOT NULL DEFAULT 1,
    weekdays   TEXT NOT NULL DEFAULT '1,2,3,4,5,6',
    archived   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quests (
    id             INTEGER PRIMARY KEY,
    template_id    INTEGER REFERENCES quest_templates(id),
    day            TEXT NOT NULL,
    title          TEXT NOT NULL,
    skill_id       INTEGER REFERENCES skills(id),
    verify         TEXT NOT NULL,
    rule_json      TEXT,
    required       INTEGER NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done')),
    completed_at   TEXT,
    completed_via  TEXT,
    proof_id       INTEGER REFERENCES attachments(id),
    UNIQUE (template_id, day)
);

CREATE TABLE IF NOT EXISTS sessions (
    id            INTEGER PRIMARY KEY,
    skill_id      INTEGER NOT NULL REFERENCES skills(id),
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    begin_action  TEXT NOT NULL DEFAULT '',
    end_action    TEXT NOT NULL DEFAULT '',
    note          TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS phone_usage (
    day      TEXT NOT NULL,
    package  TEXT NOT NULL,
    label    TEXT,
    seconds  INTEGER NOT NULL,
    PRIMARY KEY (day, package)
);

CREATE TABLE IF NOT EXISTS gate_events (
    id          INTEGER PRIMARY KEY,
    type        TEXT NOT NULL,
    reason      TEXT,
    device_id   INTEGER REFERENCES devices(id),
    created_at  TEXT NOT NULL,
    expires_at  TEXT
);
