"""Database schema definitions.

All CREATE TABLE statements live here. The schema mirrors the domain models
in models/ but is designed for SQLite storage and efficient querying.
"""

SCHEMA_VERSION = 2

# ── V1 base tables ──────────────────────────────────────────────────────

SCHEMA_V1 = """
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

# ── V2 adds sources & citations ─────────────────────────────────────────

SCHEMA_V2 = """
-- Sources: documents, letters, oral history, public records, etc.
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'other'
        CHECK (source_type IN (
            'document', 'letter', 'oral', 'public', 'direct', 'other'
        )),
    author TEXT,
    date TEXT,
    description TEXT DEFAULT '',
    url TEXT
);

-- Citations: link a specific fact to a source
CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL
        CHECK (entity_type IN ('person', 'relationship', 'union', 'event')),
    entity_id TEXT NOT NULL,
    field_name TEXT,               -- optional: 'birth_date', 'surname', etc.
    excerpt TEXT DEFAULT '',       -- relevant quote from the source
    confidence TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (confidence IN ('confirmed', 'probable', 'uncertain', 'conflicting')),
    notes TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);
CREATE INDEX IF NOT EXISTS idx_citations_entity ON citations(entity_type, entity_id);
"""

# Combined for fresh installs
SCHEMA_SQL = SCHEMA_V1 + SCHEMA_V2

# Migration map: version → SQL to apply
MIGRATIONS = {
    2: SCHEMA_V2,
}
