"""Database schema definitions.

All CREATE TABLE statements live here. The schema mirrors the domain models
in models/ but is designed for SQLite storage and efficient querying.
"""

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);

-- People: the nodes of the family graph
CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    given_name TEXT NOT NULL,
    surname TEXT NOT NULL,
    gender TEXT NOT NULL DEFAULT 'unknown'
        CHECK (gender IN ('male', 'female', 'other', 'unknown')),
    birth_date TEXT,
    birth_place TEXT,
    death_date TEXT,
    death_place TEXT,
    maiden_name TEXT,
    nicknames TEXT DEFAULT '[]',       -- JSON array of strings
    notes TEXT DEFAULT '',
    photo_paths TEXT DEFAULT '[]',     -- JSON array of strings
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Parent → Child edges (the backbone of the tree)
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    child_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    rel_type TEXT NOT NULL DEFAULT 'biological'
        CHECK (rel_type IN ('biological', 'adoptive', 'step', 'foster')),
    UNIQUE(parent_id, child_id)
);

-- Marriage / partnership bonds
CREATE TABLE IF NOT EXISTS unions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner1_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    partner2_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    union_date TEXT,
    union_place TEXT,
    end_date TEXT,
    end_reason TEXT,
    notes TEXT DEFAULT ''
);

-- Life events attached to a person
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'birth', 'death', 'marriage', 'divorce',
            'immigration', 'emigration', 'naturalization',
            'education', 'career', 'military',
            'residence', 'religion', 'medical', 'custom'
        )),
    date TEXT,
    end_date TEXT,
    place TEXT,
    description TEXT DEFAULT '',
    source TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_relationships_parent ON relationships(parent_id);
CREATE INDEX IF NOT EXISTS idx_relationships_child ON relationships(child_id);
CREATE INDEX IF NOT EXISTS idx_unions_partner1 ON unions(partner1_id);
CREATE INDEX IF NOT EXISTS idx_unions_partner2 ON unions(partner2_id);
CREATE INDEX IF NOT EXISTS idx_events_person ON events(person_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_people_surname ON people(surname);
CREATE INDEX IF NOT EXISTS idx_people_birth_date ON people(birth_date);
"""
