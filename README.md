# Family Tree

A structured genealogy project — modeling family history, lineage, and relationships to understand where we come from.

## What This Models

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
└── Sources
    ├── documents (birth certificates, ship manifests, census)
    ├── photos
    └── oral history notes
```

## Key Relationships

The family tree is a **directed acyclic graph** (technically — ignoring very distant cousin marriages):

- **Parent → Child**: The fundamental edge. Everything else derives from this.
- **Partners**: Marriage/partnership links between two people (not parent-child).
- **Siblings**: Inferred — share at least one parent.
- **Extended family**: Computed by graph traversal:
  - Grandparent: parent's parent
  - Uncle/Aunt: parent's sibling
  - Cousin: parent's sibling's child
  - Nth cousin M times removed: precise computation via common ancestor distance

## Privacy

⚠️ **This repo is private and must stay private.**

- Real family data is loaded at runtime from `data/` (gitignored)
- Test fixtures use synthetic/example names only
- No PII in committed code

## Project Structure

```
src/
├── models/        # Person, Relationship, Event, FamilyTree
├── traversal/     # Ancestor/descendant walks, relationship calculator
└── import_export/ # GEDCOM import, JSON export, timeline generation
tests/             # Test suite (synthetic data only)
data/              # Real family data (gitignored)
docs/              # Documentation, research notes
```

## Data Format

Family data lives in `data/family.json` (gitignored). The schema:

```json
{
  "people": [
    {
      "id": "p1",
      "given_name": "...",
      "surname": "...",
      "birth_date": "1920-03-15",
      "birth_place": "Kyiv, Ukraine",
      "death_date": "2001-07-22",
      "notes": "Immigrated to US in 1948..."
    }
  ],
  "relationships": [
    {"type": "parent_child", "parent_id": "p1", "child_id": "p2"},
    {"type": "marriage", "partner1_id": "p1", "partner2_id": "p3", "date": "1945-06-10"}
  ]
}
```

## Status

🚧 Building the foundational data model.
