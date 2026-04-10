# Family Tree

An interactive genealogy app — model your family history, visualize relationships, and explore a timeline of life events.

![Python](https://img.shields.io/badge/python-3.11+-blue) ![Flask](https://img.shields.io/badge/flask-web%20dashboard-green) ![D3](https://img.shields.io/badge/d3.js-visualizations-orange)

## Features

- **Interactive tree** — D3-powered family tree with expandable generations
- **Timeline** — chronological view of births, deaths, immigration, careers, education
- **Relationship calculator** — "How are these two people related?"
- **Heritage map** — immigration flows colored by region of origin
- **Photo gallery** — attach photos to people and see them in context
- **GEDCOM import** — load data from standard genealogy software
- **Theming** — full dark/light mode with customizable color palettes

## Quick Start

```bash
# Clone and set up
git clone https://github.com/dmoskov/family-tree.git
cd family-tree
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Seed with example data (Longfellow descendants — public historical data)
python3 data/seed_longfellow.py

# Start the web dashboard
python3 -m cli serve
# Open http://localhost:8000
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

### 4. Add photos (optional)

Place photos in `private/photos/`. The web server automatically serves them at `/photos/<filename>`.

To link photos to people, create a photo-attachment script in `private/data/` (see the seed scripts for the pattern of adding photo references).

### 5. Start exploring

```bash
python3 -m cli serve          # Web dashboard at http://localhost:8000
python3 -m cli list           # List all people
python3 -m cli show <id>      # Show details for a person
python3 -m cli relationship <id1> <id2>  # How are they related?
python3 -m cli timeline --all # Full timeline
python3 -m cli stats          # Family stats
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
├── app.js           # D3 tree, timeline, relationship calculator
├── styles.css
└── family-config.example.json  # Template — copy to private/config/

data/                # Seed scripts & example data
├── example_family.json
└── seed_longfellow.py  # Example: public historical family

tests/               # Test suite (synthetic data only)
deploy/              # EC2 deployment scripts (nginx, gunicorn, systemd)

private/             # YOUR family data (gitignored)
├── config/family-config.json
├── data/seed_yourfamily.py
├── photos/
└── documents/
```

## Deployment

See `deploy/` for scripts to deploy on an EC2 instance with nginx + gunicorn.

```bash
# Build and run with Docker
docker build -t family-tree .
docker run -p 8000:8000 -v $(pwd)/private:/app/private family-tree
```

## License

Private project. The application code is shareable; family data is not.
