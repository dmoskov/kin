# Family Tree

An interactive genealogy app — model your family history, visualize relationships, and explore a timeline of life events.

![Python](https://img.shields.io/badge/python-3.11+-blue) ![Flask](https://img.shields.io/badge/flask-web%20dashboard-green) ![D3](https://img.shields.io/badge/d3.js-visualizations-orange)

## Features

- **Interactive tree** — D3-powered family tree with expandable generations and fog-of-war dimming of distant branches
- **Timeline** — chronological view of births, deaths, immigration, careers, education; click any entry to jump to that person
- **Relationship calculator** — "How are these two people related?" with a full chain explanation
- **Heritage map** — immigration flows colored by region of origin, with animated time-lapse
- **In-browser editing** — add parents, siblings, children, and partners directly from the tree; edit a person's name, dates, and places without touching a seed script; full undo/redo
- **Photo gallery** — upload photos in the browser, attach them to people, add captions; full-screen lightbox and timeline gallery view; optional Google Photos import
- **Document parsing** — upload a birth certificate / obituary / photo and have the AI extract people, dates, and relationships for review before applying
- **News article tracking** — link newspaper clippings and articles to the people they mention
- **GEDCOM import** — load data from standard genealogy software
- **Sources & citations** — attach documentary evidence to any fact with confidence levels
- **Theming** — full dark/light mode with customizable color palettes

## Quick Start

### Option A: Docker (recommended)

```bash
git clone https://github.com/dmoskov/family-tree.git
cd family-tree
docker compose up
# Open http://localhost:8000
```

That's it — the app starts with an empty tree and walks you through adding your first family members.

### Option B: Local Python

```bash
git clone https://github.com/dmoskov/family-tree.git
cd family-tree
git config core.hooksPath .githooks   # enable pre-commit PII guard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Start the web dashboard
python3 -m cli serve
# Open http://localhost:8000
```

You can also seed with example data to see a populated tree:

```bash
python3 data/seed_longfellow.py  # Longfellow descendants — public historical data
```

## Adding Your Own Family

All personal data lives in a `private/` directory that is **gitignored** — your family information never touches version control.

### 1. Create the private directory

```bash
mkdir -p private/{data,photos,config,documents}
```

### 2. Configure your family

Copy the example config and customize it:

```bash
cp web/family-config.example.json private/config/family-config.json
```

Edit `private/config/family-config.json`:

```jsonc
{
  "familyName": "Your Family Name",
  "subtitle": "An optional subtitle",
  "centerIdA": "person-id-for-tree-center",  // person ID to center the tree on
  "centerIdB": "partner-id",                  // optional second center
  "heritage": [
    { "region": "Italy", "color": "#b33a3a", "match": ["Rome", "Naples", "Sicily"] }
  ]
  // ... fonts, palette, etc.
}
```

### 3. Add your family data

You have three options:

#### Option A: Write a seed script (recommended for new trees)

Create `private/data/seed_yourfamily.py` following the pattern in `data/seed_longfellow.py`:

```python
from models.person import Gender, Person
from models.relationship import Relationship, Union
from models.event import EventType, LifeEvent
from models.tree import FamilyTree

tree = FamilyTree()

tree.add_person(Person(
    id="grandma-jones",
    given_name="Margaret",
    surname="Jones",
    gender=Gender.FEMALE,
    birth_date="1935-03-15",
    birth_place="Chicago, IL",
))
# ... add more people, relationships, unions, events
```

Then run it:
```bash
python3 private/data/seed_yourfamily.py
```

#### Option B: Import a JSON file

Create a `data/family.json` (gitignored) following this schema:

```json
{
  "people": [
    {
      "id": "p1",
      "given_name": "Margaret",
      "surname": "Jones",
      "gender": "female",
      "birth_date": "1935-03-15",
      "birth_place": "Chicago, IL"
    }
  ],
  "relationships": [
    { "parent_id": "p1", "child_id": "p2" }
  ],
  "unions": [
    { "partner1_id": "p1", "partner2_id": "p3", "union_date": "1958-06-10" }
  ],
  "events": [
    { "person_id": "p1", "event_type": "immigration", "date": "1920", "place": "Ellis Island, NY" }
  ]
}
```

See `data/example_family.json` for a complete working example.

#### Option C: Import a GEDCOM file

If you have data from Ancestry, MyHeritage, or other genealogy software:

```bash
python3 -m cli import path/to/export.ged
```

### 4. Add photos and documents from the browser

Once the dashboard is running at `http://localhost:8000`, you can upload content
directly from the UI — no scripts or `scp` required. Anything you upload lands
under `private/photos/` or `private/documents/` (both gitignored).

#### Attaching photos to a person

1. Click a person in the tree or timeline to open their side panel.
2. Click **Photos → + Manage Photos**. The photo picker opens.
3. Upload new photos by either:
   - **Clicking** the "Click or drag photos here" zone and choosing files, or
   - **Dragging and dropping** one or more images onto the zone.
4. Each uploaded photo is auto-assigned to the current person and appears with a
   green check.
5. Click any existing photo tile to **toggle** whether it's attached to this person
   (the same photo can be attached to multiple people).
6. Click an attached photo's caption field to add a caption like "Easter 1987".
   Captions save automatically on blur or when you press Enter.

Supported image types: **JPG, JPEG, PNG, WEBP, GIF**. Maximum size per file:
**8 MB** (configurable via the `MAX_PHOTO_BYTES` env var). Files whose contents
don't match their extension (e.g. an `.exe` renamed to `.jpg`) are rejected.

Error messages from the server — invalid type, too large, empty file, etc. —
are surfaced as red toasts in the bottom-right corner.

#### AI document parsing

For birth certificates, obituaries, family photos with caption text, or similar
records, the **Documents** panel can OCR the file and propose changes:

1. Click **📄 Upload Document** in the top toolbar.
2. Drop or select an image (JPG/PNG/WEBP/GIF) or PDF. Max **50 MB**
   (`MAX_DOC_BYTES`).
3. Once uploaded, click **Parse with AI**. The server runs the document through
   an LLM and returns proposed people / relationships / events.
4. Review the proposed changes in the modal — you can edit any field, mark
   proposed people as "existing" (matched to someone in the tree) or "new",
   then **Apply** to write them into the database.

Uploaded documents are stored in `private/documents/` and tracked in the
`documents` table with status `uploaded → parsing → parsed → applied`. Nothing
is written to the tree until you click Apply.

#### Scripted photo attachment (still supported)

If you'd rather attach photos in bulk from a seed script, drop them into
`private/photos/` and reference them by path in a Person's `photo_paths`
list. See the seed scripts for the pattern.

### 5. Manage people from the browser

You can add new people, edit existing details, and wire up relationships directly
from the tree — no seed scripts required.

#### Adding a relative

1. Click any person in the tree to open their side panel.
2. Scroll to **Add Relative** and click **+ Parent**, **+ Sibling**, **+ Child**,
   or **+ Partner**.
3. Fill in the name, gender, birth year, and (optionally) death year, then click
   **Add [Relative type]**.
4. The new person is saved to the database and the tree re-renders immediately.

For siblings, the new person is automatically linked to all of the focused
person's existing parents. If the focused person has no parents yet, the sibling
is created without parent links (you can add parents later).

#### Editing a person

1. Click a person in the tree to open their side panel.
2. Click **Edit** (below their name and gender badge).
3. Update any fields — first name, last name, gender, birth date, birth place,
   death date, death place — then click **Save**.

Dates accept partial formats: `1987`, `1987-05`, and `1987-05-12` are all valid.
Leave a field blank (or clear it) to remove the value.

### 6. Start exploring

```bash
python3 -m cli serve          # Web dashboard at http://localhost:8000
python3 -m cli list           # List all people
python3 -m cli show <id>      # Show details for a person
python3 -m cli relationship <id1> <id2>  # How are they related?
python3 -m cli timeline --all # Full timeline
python3 -m cli stats          # Family stats
python3 -m cli audit          # Check tree for integrity issues (--fix to auto-repair)
python3 -m cli sources        # List all sources
python3 -m cli add-source     # Add a documentary source
python3 -m cli cite           # Attach a source citation to a fact
```

## Data Model

```
Person
├── names (given, surname, maiden, nicknames)
├── vital dates (birth, death)
├── birthplace / places lived
├── bio / notes / stories
│
├── Parents (biological, adoptive, step)
├── Children
├── Partners (marriages, partnerships)
│   ├── union date, location
│   └── end date (divorce, death)
│
├── Life Events
│   ├── birth, death, marriage, divorce
│   ├── immigration / emigration
│   ├── education, career
│   └── custom milestones
│
└── Sources & Citations
    ├── documents (birth certificates, ship manifests, census)
    ├── photos
    └── oral history notes
```

## Project Structure

```
src/
├── models/          # Person, Relationship, Event, Source, FamilyTree
├── database/        # SQLite/PostgreSQL via repository pattern
├── traversal/       # Ancestor/descendant walks, relationship calculator
├── import_export/   # GEDCOM import, JSON I/O
├── web_server.py    # Flask app (API + static files)
└── cli.py           # Command-line interface

web/                 # Dashboard frontend
├── index.html
├── styles.css
├── family-config.example.json  # Template — copy to private/config/
└── js/              # Modular frontend (loaded in order by index.html)
    ├── 00-state.js  # Shared state
    ├── 01-core.js … 08-map.js  # Tree, timeline, map, relationship calc
    └── 09-init.js … 99-main.js # Auth, photos, documents, gallery, lightbox

data/                # Seed scripts & example data
├── example_family.json
└── seed_longfellow.py  # Example: public historical family

tests/               # Test suite (synthetic data only)
deploy/              # Deployment scripts and config (nginx, gunicorn, systemd, .env.example)

private/             # YOUR family data (gitignored)
├── config/family-config.json
├── data/seed_yourfamily.py
├── photos/
└── documents/
```

## Deployment

### Production (EC2)

The app runs on an EC2 instance with nginx + gunicorn. Before deploying, fill in your instance details in `deploy/deploy.sh` and your domain in `deploy/nginx.conf`.

**Deploy code changes:**

```bash
bash deploy/deploy.sh
```

This script:
1. Pushes your SSH key via EC2 Instance Connect (requires AWS CLI)
2. `rsync`s `web/`, `src/`, `private/config/`, `private/photos/`, and `requirements.txt` to the server
3. Installs Python dependencies
4. Restarts the `familytree` systemd service

**Requirements:**
- AWS CLI with `ec2-instance-connect` permissions
- SSH key pair configured in `deploy/deploy.sh`
- `rsync` installed locally

**Important notes:**
- `private/config/family-config.json` is synced local → server on each deploy. Keep the local copy as the source of truth.
- Photos sync is additive (no `--delete`) — photos uploaded via the web UI on the server are preserved.
- `private/` is gitignored; config and photos never go into the repo.

**First-time setup:**
```bash
# On the EC2 instance:
sudo bash deploy/setup.sh
```

### Continuous deployment (CI/CD)

Pushes are validated and shipped automatically:

- **`ci.yml`** runs lint (ruff + mypy), pytest, vitest, and a headless smoke test on every push to `main` and `task/**`, and on PRs to `main`.
- **`auto-merge.yml`** — when CI passes on a `task/**` branch, it's merged into `main` automatically (a merge commit, no PR) and deployed. Conflicting branches are left for a human.
- **`deploy.yml` / `deploy-reusable.yml`** — when CI passes on `main` (or via manual `workflow_dispatch`), the bundle is built and `web/` + `src/` are rsynced to the server, deps reinstalled, and the service restarted and health-checked.

Server identifiers are stored as repo secrets (`DEPLOY_HOST`, `DEPLOY_SSH_KEY`), never committed. `deploy/deploy.sh` remains available for manual/emergency deploys.

### Local (Docker)

```bash
# Quick start with Docker Compose
docker compose up

# Or build and run manually
docker build -t family-tree .
docker run -p 8000:8000 -v $(pwd)/private:/app/private family-tree
```

### Environment variables

| Variable           | Purpose                                                | Default              |
| ------------------ | ------------------------------------------------------ | -------------------- |
| `DATABASE_URL`     | Postgres DSN. If unset, falls back to local SQLite.    | _(SQLite)_           |
| `FAMILY_TREE_DB`   | SQLite path override (local dev only).                 | `data/family.db`     |
| `SECRET_KEY`       | Flask session key — set in production.                 | `dev-secret-...`     |
| `MAX_PHOTO_BYTES`  | Per-file cap for `/api/photos/upload`.                 | `8388608` (8 MB)     |
| `MAX_DOC_BYTES`    | Per-file cap for `/api/documents/upload`.              | `52428800` (50 MB)   |
| `GOOGLE_CLIENT_ID` | Enables Google Sign-In on the dashboard.               | _(sign-in disabled)_ |
| `EDITORS`          | Comma-separated Gmail addresses with edit access. Anyone not listed can view but not edit. Editors may sign in even without a person record in the tree. Example: `alice@gmail.com,bob@gmail.com` | _(unset — editing unrestricted)_ |
| `ANTHROPIC_API_KEY`| Enables **Parse with AI** for uploaded documents.      | _(parsing disabled)_ |
| `ADMIN_PERSON_ID`  | Person ID that can assign emails to tree members and manage non-family editors (assistants, researchers) via the UI. | _(feature disabled)_ |

## License

MIT. Family data stored in `private/` is yours and never touches version control.
