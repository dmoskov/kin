"""Database schema definitions.

All CREATE TABLE statements live here for both SQLite and PostgreSQL.
The schema mirrors the domain models in models/ and is designed for
efficient querying.
"""

SCHEMA_VERSION = 16

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
    visibility TEXT NOT NULL DEFAULT 'everyone'
        CHECK (visibility IN ('everyone', 'self_and_children', 'private')),
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


SCHEMA_V4 = """
ALTER TABLE people ADD COLUMN photo_captions TEXT DEFAULT '{}';
"""

SCHEMA_V5 = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    uploaded_by TEXT REFERENCES people(id),
    uploaded_at TEXT DEFAULT (datetime('now')),
    parsed_data TEXT DEFAULT '{}',
    status TEXT DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'parsing', 'parsed', 'applied', 'error'))
);
"""

SCHEMA_V6 = """
CREATE TABLE IF NOT EXISTS geocode_cache (
    place TEXT PRIMARY KEY,
    lat   REAL,
    lng   REAL,
    fetched_at TEXT DEFAULT (datetime('now'))
);
"""

SCHEMA_V7 = """
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    date TEXT,
    date_circa INTEGER DEFAULT 0,
    place TEXT,
    photo_type TEXT DEFAULT 'photo'
        CHECK (photo_type IN ('portrait', 'group', 'document', 'headstone', 'photo')),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS person_photos (
    person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    is_profile INTEGER DEFAULT 0,
    display_order INTEGER DEFAULT 0,
    caption TEXT DEFAULT '',
    UNIQUE(person_id, photo_id)
);

CREATE INDEX IF NOT EXISTS idx_person_photos_person ON person_photos(person_id);
CREATE INDEX IF NOT EXISTS idx_person_photos_photo ON person_photos(photo_id);
CREATE INDEX IF NOT EXISTS idx_photos_date ON photos(date);
CREATE INDEX IF NOT EXISTS idx_photos_place ON photos(place);
"""

SCHEMA_V8 = """
CREATE TABLE IF NOT EXISTS face_regions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    x REAL NOT NULL,
    y REAL NOT NULL,
    w REAL NOT NULL,
    h REAL NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(photo_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_face_regions_photo ON face_regions(photo_id);
CREATE INDEX IF NOT EXISTS idx_face_regions_person ON face_regions(person_id);

ALTER TABLE person_photos ADD COLUMN crop_x REAL;
ALTER TABLE person_photos ADD COLUMN crop_y REAL;
ALTER TABLE person_photos ADD COLUMN crop_w REAL;
ALTER TABLE person_photos ADD COLUMN crop_h REAL;
"""

SCHEMA_V9 = """
-- Recreate face_regions without UNIQUE(photo_id, person_id) to allow
-- multiple face tags for the same person in montage photos.
CREATE TABLE IF NOT EXISTS face_regions_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    x REAL NOT NULL,
    y REAL NOT NULL,
    w REAL NOT NULL,
    h REAL NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
INSERT INTO face_regions_new SELECT * FROM face_regions;
DROP TABLE face_regions;
ALTER TABLE face_regions_new RENAME TO face_regions;
CREATE INDEX IF NOT EXISTS idx_face_regions_photo ON face_regions(photo_id);
CREATE INDEX IF NOT EXISTS idx_face_regions_person ON face_regions(person_id);
"""

SCHEMA_V10 = """
ALTER TABLE photos ADD COLUMN lat REAL;
ALTER TABLE photos ADD COLUMN lng REAL;
CREATE INDEX IF NOT EXISTS idx_photos_lat_lng ON photos(lat, lng);
"""

SCHEMA_V11 = """
CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    start_page INTEGER NOT NULL,
    end_page INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'text' CHECK (mode IN ('text', 'image')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'error')),
    parsed_data TEXT DEFAULT '{}',
    error_message TEXT,
    UNIQUE(document_id, chunk_index)
);

ALTER TABLE documents ADD COLUMN total_chunks INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN chunks_done INTEGER DEFAULT 0;
"""

SCHEMA_V12 = """
CREATE TABLE IF NOT EXISTS news_articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT,
    publication TEXT,
    date TEXT,
    summary TEXT DEFAULT '',
    photo_url TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS person_articles (
    person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    article_id TEXT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    UNIQUE(person_id, article_id)
);

CREATE INDEX IF NOT EXISTS idx_person_articles_person ON person_articles(person_id);
CREATE INDEX IF NOT EXISTS idx_person_articles_article ON person_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_news_articles_date ON news_articles(date);
"""

SCHEMA_V13 = """
CREATE TABLE IF NOT EXISTS undo_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT (datetime('now')),
    kind TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""

SCHEMA_V14 = """
ALTER TABLE relationships ADD COLUMN visibility TEXT NOT NULL DEFAULT 'everyone'
    CHECK (visibility IN ('everyone', 'self_and_children', 'private'));
"""

SCHEMA_V15 = """
ALTER TABLE events ADD COLUMN date_circa INTEGER DEFAULT 0;
"""

SCHEMA_V16 = """
CREATE TABLE IF NOT EXISTS tree_editors (
    email TEXT PRIMARY KEY,
    role TEXT NOT NULL DEFAULT 'editor'
        CHECK (role IN ('owner', 'editor', 'assistant', 'researcher')),
    name TEXT DEFAULT '',
    invited_by TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

SCHEMA_SQL = (
    SCHEMA_V1
    + SCHEMA_V2
    + SCHEMA_V3
    + SCHEMA_V4
    + SCHEMA_V5
    + SCHEMA_V6
    + SCHEMA_V7
    + SCHEMA_V8
    + SCHEMA_V9
    + SCHEMA_V10
    + SCHEMA_V11
    + SCHEMA_V12
    + SCHEMA_V13
    + SCHEMA_V15
    + SCHEMA_V16
)

MIGRATIONS = {
    2: SCHEMA_V2,
    3: SCHEMA_V3,
    4: SCHEMA_V4,
    5: SCHEMA_V5,
    6: SCHEMA_V6,
    7: SCHEMA_V7,
    8: SCHEMA_V8,
    9: SCHEMA_V9,
    10: SCHEMA_V10,
    11: SCHEMA_V11,
    12: SCHEMA_V12,
    13: SCHEMA_V13,
    14: SCHEMA_V14,
    15: SCHEMA_V15,
    16: SCHEMA_V16,
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
    visibility TEXT NOT NULL DEFAULT 'everyone'
        CHECK (visibility IN ('everyone', 'self_and_children', 'private')),
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

PG_SCHEMA_V4 = """
ALTER TABLE people ADD COLUMN IF NOT EXISTS photo_captions TEXT DEFAULT '{}';
"""

PG_SCHEMA_V5 = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    uploaded_by TEXT REFERENCES people(id),
    uploaded_at TIMESTAMP DEFAULT NOW(),
    parsed_data TEXT DEFAULT '{}',
    status TEXT DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'parsing', 'parsed', 'applied', 'error'))
);
"""

PG_SCHEMA_V6 = """
CREATE TABLE IF NOT EXISTS geocode_cache (
    place TEXT PRIMARY KEY,
    lat   DOUBLE PRECISION,
    lng   DOUBLE PRECISION,
    fetched_at TIMESTAMP DEFAULT NOW()
);
"""

PG_SCHEMA_V7 = """
CREATE TABLE IF NOT EXISTS photos (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    date TEXT,
    date_circa BOOLEAN DEFAULT FALSE,
    place TEXT,
    photo_type TEXT DEFAULT 'photo'
        CHECK (photo_type IN ('portrait', 'group', 'document', 'headstone', 'photo')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS person_photos (
    person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    is_profile BOOLEAN DEFAULT FALSE,
    display_order INTEGER DEFAULT 0,
    caption TEXT DEFAULT '',
    UNIQUE(person_id, photo_id)
);

CREATE INDEX IF NOT EXISTS idx_person_photos_person ON person_photos(person_id);
CREATE INDEX IF NOT EXISTS idx_person_photos_photo ON person_photos(photo_id);
CREATE INDEX IF NOT EXISTS idx_photos_date ON photos(date);
CREATE INDEX IF NOT EXISTS idx_photos_place ON photos(place);
"""

PG_SCHEMA_V8 = """
CREATE TABLE IF NOT EXISTS face_regions (
    id SERIAL PRIMARY KEY,
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    x DOUBLE PRECISION NOT NULL,
    y DOUBLE PRECISION NOT NULL,
    w DOUBLE PRECISION NOT NULL,
    h DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(photo_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_face_regions_photo ON face_regions(photo_id);
CREATE INDEX IF NOT EXISTS idx_face_regions_person ON face_regions(person_id);

ALTER TABLE person_photos ADD COLUMN IF NOT EXISTS crop_x DOUBLE PRECISION;
ALTER TABLE person_photos ADD COLUMN IF NOT EXISTS crop_y DOUBLE PRECISION;
ALTER TABLE person_photos ADD COLUMN IF NOT EXISTS crop_w DOUBLE PRECISION;
ALTER TABLE person_photos ADD COLUMN IF NOT EXISTS crop_h DOUBLE PRECISION;
"""

PG_SCHEMA_V9 = """
ALTER TABLE face_regions DROP CONSTRAINT IF EXISTS face_regions_photo_id_person_id_key;
"""

PG_SCHEMA_V10 = """
ALTER TABLE photos ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;
ALTER TABLE photos ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION;
CREATE INDEX IF NOT EXISTS idx_photos_lat_lng ON photos(lat, lng);
"""

PG_SCHEMA_V11 = """
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    start_page INTEGER NOT NULL,
    end_page INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'text' CHECK (mode IN ('text', 'image')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'error')),
    parsed_data TEXT DEFAULT '{}',
    error_message TEXT,
    UNIQUE(document_id, chunk_index)
);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS total_chunks INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunks_done INTEGER DEFAULT 0;
"""

PG_SCHEMA_V12 = """
CREATE TABLE IF NOT EXISTS news_articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT,
    publication TEXT,
    date TEXT,
    summary TEXT DEFAULT '',
    photo_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS person_articles (
    person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    article_id TEXT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    UNIQUE(person_id, article_id)
);

CREATE INDEX IF NOT EXISTS idx_person_articles_person ON person_articles(person_id);
CREATE INDEX IF NOT EXISTS idx_person_articles_article ON person_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_news_articles_date ON news_articles(date);
"""

PG_SCHEMA_V13 = """
CREATE TABLE IF NOT EXISTS undo_log (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    kind TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""

PG_SCHEMA_V14 = """
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'everyone'
    CHECK (visibility IN ('everyone', 'self_and_children', 'private'));
"""

PG_SCHEMA_V15 = """
ALTER TABLE events ADD COLUMN IF NOT EXISTS date_circa BOOLEAN DEFAULT FALSE;
"""

PG_SCHEMA_V16 = """
CREATE TABLE IF NOT EXISTS tree_editors (
    email TEXT PRIMARY KEY,
    role TEXT NOT NULL DEFAULT 'editor'
        CHECK (role IN ('owner', 'editor', 'assistant', 'researcher')),
    name TEXT DEFAULT '',
    invited_by TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

PG_SCHEMA_SQL = (
    PG_SCHEMA_V1
    + PG_SCHEMA_V2
    + PG_SCHEMA_V3
    + PG_SCHEMA_V4
    + PG_SCHEMA_V5
    + PG_SCHEMA_V6
    + PG_SCHEMA_V7
    + PG_SCHEMA_V8
    + PG_SCHEMA_V9
    + PG_SCHEMA_V10
    + PG_SCHEMA_V11
    + PG_SCHEMA_V12
    + PG_SCHEMA_V13
    + PG_SCHEMA_V15
    + PG_SCHEMA_V16
)

PG_MIGRATIONS = {
    2: PG_SCHEMA_V2,
    3: PG_SCHEMA_V3,
    4: PG_SCHEMA_V4,
    5: PG_SCHEMA_V5,
    6: PG_SCHEMA_V6,
    7: PG_SCHEMA_V7,
    8: PG_SCHEMA_V8,
    9: PG_SCHEMA_V9,
    10: PG_SCHEMA_V10,
    11: PG_SCHEMA_V11,
    12: PG_SCHEMA_V12,
    13: PG_SCHEMA_V13,
    14: PG_SCHEMA_V14,
    15: PG_SCHEMA_V15,
    16: PG_SCHEMA_V16,
}
