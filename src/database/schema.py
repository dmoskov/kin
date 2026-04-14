"""Database schema definitions.

All CREATE TABLE statements live here for both SQLite and PostgreSQL.
The schema mirrors the domain models in models/ and is designed for
efficient querying.
"""

SCHEMA_VERSION = 3

# ═══════════════════════════════════════════════════════════════════════
# SQLite schema (local dev / tests)
# ═══════════════════════════════════════════════════════════════════════

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);

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
    nicknames TEXT DEFAULT '[]',
    notes TEXT DEFAULT '',
    photo_paths TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    child_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    rel_type TEXT NOT NULL DEFAULT 'biological'
        CHECK (rel_type IN ('biological', 'adoptive', 'step', 'foster')),
    UNIQUE(parent_id, child_id)
);

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

CREATE INDEX IF NOT EXISTS idx_relationships_parent ON relationships(parent_id);
CREATE INDEX IF NOT EXISTS idx_relationships_child ON relationships(child_id);
CREATE INDEX IF NOT EXISTS idx_unions_partner1 ON unions(partner1_id);
CREATE INDEX IF NOT EXISTS idx_unions_partner2 ON unions(partner2_id);
CREATE INDEX IF NOT EXISTS idx_events_person ON events(person_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_people_surname ON people(surname);
CREATE INDEX IF NOT EXISTS idx_people_birth_date ON people(birth_date);
"""

SCHEMA_V2 = """
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

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL
        CHECK (entity_type IN ('person', 'relationship', 'union', 'event')),
    entity_id TEXT NOT NULL,
    field_name TEXT,
    excerpt TEXT DEFAULT '',
    confidence TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (confidence IN ('confirmed', 'probable', 'uncertain', 'conflicting')),
    notes TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);
CREATE INDEX IF NOT EXISTS idx_citations_entity ON citations(entity_type, entity_id);
"""

SCHEMA_V3 = """
ALTER TABLE people ADD COLUMN email TEXT;
"""

# Known email addresses to seed after V3 migration
SEED_EMAILS = {
    "dustin": "REDACTED_EMAIL",
    "tree-member-1": "REDACTED_EMAIL",
    "cari": "REDACTED_EMAIL",
    "tree-member-2": "REDACTED_EMAIL",
    "tree-member-3": "REDACTED_EMAIL",
    "tree-member-4": "REDACTED_EMAIL",
}

SCHEMA_SQL = SCHEMA_V1 + SCHEMA_V2 + SCHEMA_V3

MIGRATIONS = {
    2: SCHEMA_V2,
    3: SCHEMA_V3,
}


# ═══════════════════════════════════════════════════════════════════════
# PostgreSQL schema (production)
# ═══════════════════════════════════════════════════════════════════════

PG_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW()
);

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
    nicknames TEXT DEFAULT '[]',
    notes TEXT DEFAULT '',
    photo_paths TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS relationships (
    id SERIAL PRIMARY KEY,
    parent_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    child_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    rel_type TEXT NOT NULL DEFAULT 'biological'
        CHECK (rel_type IN ('biological', 'adoptive', 'step', 'foster')),
    UNIQUE(parent_id, child_id)
);

CREATE TABLE IF NOT EXISTS unions (
    id SERIAL PRIMARY KEY,
    partner1_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    partner2_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    union_date TEXT,
    union_place TEXT,
    end_date TEXT,
    end_reason TEXT,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
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

CREATE INDEX IF NOT EXISTS idx_relationships_parent ON relationships(parent_id);
CREATE INDEX IF NOT EXISTS idx_relationships_child ON relationships(child_id);
CREATE INDEX IF NOT EXISTS idx_unions_partner1 ON unions(partner1_id);
CREATE INDEX IF NOT EXISTS idx_unions_partner2 ON unions(partner2_id);
CREATE INDEX IF NOT EXISTS idx_events_person ON events(person_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_people_surname ON people(surname);
CREATE INDEX IF NOT EXISTS idx_people_birth_date ON people(birth_date);
"""

PG_SCHEMA_V2 = """
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

CREATE TABLE IF NOT EXISTS citations (
    id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL
        CHECK (entity_type IN ('person', 'relationship', 'union', 'event')),
    entity_id TEXT NOT NULL,
    field_name TEXT,
    excerpt TEXT DEFAULT '',
    confidence TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (confidence IN ('confirmed', 'probable', 'uncertain', 'conflicting')),
    notes TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source_id);
CREATE INDEX IF NOT EXISTS idx_citations_entity ON citations(entity_type, entity_id);
"""

PG_SCHEMA_V3 = """
ALTER TABLE people ADD COLUMN IF NOT EXISTS email TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_people_email ON people(email) WHERE email IS NOT NULL;
"""

PG_SCHEMA_SQL = PG_SCHEMA_V1 + PG_SCHEMA_V2 + PG_SCHEMA_V3

PG_MIGRATIONS = {
    2: PG_SCHEMA_V2,
    3: PG_SCHEMA_V3,
}
