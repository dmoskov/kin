# Data Provenance Notes

Verification status and citation basis for curated facts in this project's
seed data. Modeled after the [dcc DATA_NOTES.md](https://github.com/dmoskov/dcc)
provenance discipline.

**Scope:** `data/seed_longfellow.py` — the Longfellow descendant tree, ~62
individuals across 10 generations of public historical figures.

**Last reviewed:** 2026-08-24

---

## Citation conventions

| Tag | Meaning |
|-----|---------|
| `confirmed` | Multiple independent sources agree, or a primary document |
| `probable` | Single reliable published source |
| `uncertain` | Inferred, estimated date, or single secondary reference |
| `conflicting` | Sources disagree — noted inline |
| `uncited` | Present in the seed data but no formal LifeEvent citation yet |

These map directly to the `Confidence` enum in `src/models/citation.py`.

---

## Sources

The seed script declares four sources. Each is identified by a constant used in
`LifeEvent.source` fields.

| Constant | ID | Full title | Type | Notes |
|----------|-----|-----------|------|-------|
| `SOURCE_DOC` | `longfellow-descendants-2009` | "Descendants of William Longfellow" report (4 Dec 2009) | Genealogical report | 10-generation descendant chart; primary source for the Byfield–Minnesota branch |
| `SOURCE_FARNHAM` | `farnham-2002` | *A Longfellow Genealogy* — Russell C. Farnham & Dorothy E. Crawford (2002) | Published book | 1,188 pages; covers English ancestry and American descendants; authoritative for the poet's line |
| `SOURCE_FINDAGRAVE` | `findagrave` | Find A Grave (findagrave.com) | Online public records | Cemetery records, gravestone photographs, memorial pages |
| `SOURCE_ME_HISTORICAL` | `me-historical-society` | Maine Historical Society Collections (mainehistory.org) | Institutional archive | Library and archival collections; supports Portland-area residences and civic roles |

---

## Verification status by generation

### English ancestors (pre-immigration)

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| William Longfellow Sr (b. 1619) | Birth ~1619, Horsforth, Yorkshire; d. 1676 | Farnham (2002) — cited in notes | `probable` |
| Elizabeth Thornton (b. ~1622) | Yorkshire origin; wife of William Sr | Farnham (2002) — cited in notes | `probable` |

### Generation 1 — the immigrant

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| William Longfellow (1650–1690) | Birth 20 Oct 1650, Horsforth; immigration ~1676; death 31 Oct 1690 Anticosti Island | Farnham (2002) for birth/immigration/marriage; Find A Grave Memorial #22571205 for death | `confirmed` |
| Anne Sewall | Wife of William; sister of Chief Justice Samuel Sewall | Farnham (2002); Sewall diary reference in notes | `probable` |

### Generation 2 — children of William & Anne

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| William Longfellow (b. 1679) | Birth 20 Nov 1679 | Descendant report (2009) | `uncited` — no LifeEvent |
| Stephen Longfellow (b. 1681) | Birth 10 Jan 1681 | Descendant report (2009) | `uncited` — no LifeEvent |
| Anna Longfellow (b. 1683) | Birth 3 Oct 1683 | Descendant report (2009) | `uncited` — no LifeEvent |
| Stephen Longfellow "the Blacksmith" (1685–1764) | Birth/career/church/death fully cited | Descendant report, Farnham, Find A Grave Memorial #14327894 | `confirmed` |
| Elizabeth Longfellow (b. 1688) | Birth 3 Jul 1688 | Descendant report (2009) | `uncited` — no LifeEvent |
| Nathan Longfellow (1690–1731) | Birth/residence/death cited | Descendant report + Farnham (2002) | `confirmed` |

### Generation 2b — Nathan's branch

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| Jonathan Longfellow (1714–1774) | Birth/residence/death cited | Farnham (2002) | `confirmed` |

### Generation 3 — children of Stephen "the Blacksmith"

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| Abigail Thompson | Wife of Lt. Stephen; marriage 25 Mar 1714 | Descendant report (2009) | `uncited` — no LifeEvent |
| William Longfellow (1714–1787) | Birth/marriage/death cited | Descendant report (2009) | `confirmed` |
| Anne Longfellow (1716–1792) | Birth/death dates in Person record | Descendant report (2009) | `uncited` — no LifeEvent |
| Edward Longfellow (1718–1794) | Birth/death dates in Person record | Descendant report (2009) | `uncited` — no LifeEvent |
| Sarah Longfellow (1721–1803) | Birth/death dates in Person record | Descendant report (2009) | `uncited` — no LifeEvent |
| Stephen Longfellow "the Schoolmaster" (1723–1790) | Birth/education/career/marriage/residence/death fully cited | Descendant report, Farnham, Find A Grave Memorial #101663338, ME Historical Society | `confirmed` |
| Samuel Longfellow (1725–1800) | Birth/death dates in Person record | Descendant report (2009) | `uncited` — no LifeEvent |
| Abigal Longfellow (1727–1729) | Birth/death dates in Person record | Descendant report (2009) | `uncited` — no LifeEvent |
| Elizabeth Longfellow (1732–1732) | Birth/death dates; died as infant | Descendant report (2009) | `uncited` — no LifeEvent |

### Generation 3 — Stephen "the Schoolmaster" branch (poet's line)

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| Tabitha Bragdon (d. 1777) | Death cited | Farnham (2002) | `probable` |
| Stephen Longfellow "the Judge" (1750–1824) | Birth/marriage/career/death cited | Farnham (2002) + Descendant report | `confirmed` |
| Patience Young | Wife of the Judge | Descendant report (2009) | `uncited` — no LifeEvent |

### Generation 4 — the poet's father

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| Stephen Longfellow (1776–1849) | Birth/education/career/marriage/death fully cited | Farnham (2002) + ME Historical Society | `confirmed` |
| Zilpah Wadsworth (1778–1851) | Birth/residence/death cited | Farnham (2002) + ME Historical Society | `confirmed` |
| Gen. Peleg Wadsworth (1748–1829) | Birth/military/residence/death cited | Farnham (2002) + ME Historical Society | `confirmed` |

### Generation 5 — Henry Wadsworth Longfellow and siblings

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| Henry Wadsworth Longfellow (1807–1882) | Birth/education/career/marriages/residence/publications/death fully cited (13 LifeEvents) | Farnham (2002) + ME Historical Society | `confirmed` |
| Mary Storer Potter (d. 1835) | Death cited | Farnham (2002) | `probable` |
| Fanny Appleton (1817–1861) | Birth/death cited | Farnham (2002) | `confirmed` |

### Generation 6 — children of Henry Wadsworth & Fanny Appleton

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| Charles Longfellow (1844–1893) | Eldest son | Notes only — no formal citation | `uncited` |
| Ernest Wadsworth Longfellow (1845–1921) | Second son | Notes only | `uncited` |
| Fanny Longfellow (1847–1883) | Daughter | Notes only | `uncited` |
| Alice Longfellow (1850–1928) | Lived in Craigie House; notes mention this | Notes only | `uncited` |
| Edith Longfellow (b. 1853) | Daughter | Notes only | `uncited` |
| Anne Allegra Longfellow (1855–1855) | Died as infant | Notes only | `uncited` |

### William (1714) branch — Generations 4–7

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| Hepsibah Plumer | Wife of William (1714) | Descendant report (2009) | `uncited` |
| Ann B. Longfellow (1742–1778) | Birth/death | Descendant report | `uncited` |
| Nathan Longfellow (1744–1828) | Birth/death | Descendant report | `uncited` |
| Stephen Longfellow (b. 1746) | Birth/marriage cited | Descendant report (2009) | `confirmed` |
| Jane Longfellow (1749–1760) | Birth/death; baptized | Descendant report | `uncited` |
| Abigail Longfellow (1752–1778) | Birth/death | Descendant report | `uncited` |
| William Longfellow (b. 1755) | Birth | Descendant report | `uncited` |
| Samuel Longfellow (b. 1758) | Birth | Descendant report | `uncited` |
| Benjamin Longfellow (b. 1761) | Birth | Descendant report | `uncited` |
| Mary Pritchard | Wife of Stephen (1746) | Descendant report | `uncited` |
| 9 children of Stephen & Mary (1773–1792) | Birth dates | Descendant report | `uncited` |

### Stephen (1746) branch — Generations 5–8

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| John Longfellow (1781–1828) | Birth/marriage/death cited | Descendant report (2009) | `confirmed` |
| Lydia Brown | Wife of John (1781) | Descendant report | `uncited` |
| 4 children of John & Lydia (1804–1818) | Birth dates | Descendant report | `uncited` |
| John Longfellow (1804–1829) → Mary Russel | Marriage 29 Mar 1825 | Descendant report | `uncited` |
| Mary E. Longfellow (1826–1888) | Birth/death | Descendant report | `uncited` |
| John R. Longfellow (1828–1899) | Birth/death | Descendant report | `uncited` |

### Generations 7–8 — John R. branch

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| Mary Brown | Wife of John R. | Descendant report | `uncited` |
| 6 children of John R. & Mary Brown (1848–1860) | Birth/death dates; includes twins Albert & George | Descendant report | `uncited` |
| John H. Longfellow (1850–1915) | Two marriages (Helen Preme, Viola Cambelle); 8 children | Descendant report | `uncited` |

### Generations 9–10 — Minnesota branch

| Person | Key facts | Source basis | Status |
|--------|-----------|-------------|--------|
| Mildred Rena Longfellow (1885–1976) | Residence/marriages cited | Descendant report (2009) | `confirmed` |
| Dr. Lindley A. Parkinson Sr (1863–1927) | Career/death cited | Descendant report (2009) | `confirmed` |
| Mildred E. Parkinson (1906–2005) | 1930 census/career cited | Descendant report (2009) | `confirmed` |
| Sterling T. Walters Sr (1905–1981) | 1930 census cited | Descendant report (2009) | `probable` |
| Helen May Hornsby (1913–1993) | Residence cited | Descendant report (2009) | `probable` |
| Lindley Parkinson Jr (b. 1909) | Son of Mildred Rena | Descendant report | `uncited` |
| Margaret A. Parkinson (b. 1917) | Daughter of Mildred Rena | Descendant report | `uncited` |
| Arthur R. Smith | Second husband of Mildred Rena; married 9 Jan 1934 | Descendant report | `uncited` |
| 4 children of Mildred E. & Sterling Sr (1929–1943) | Birth dates | Descendant report | `uncited` |
| 2 children of Lindley Jr & Helen May (1939, 1947) | Birth dates | Descendant report | `uncited` |

---

## Coverage summary

| Metric | Count |
|--------|-------|
| Total persons in seed data | 93 |
| Persons with formal LifeEvent citations | 21 (23%) |
| Persons with only informal notes citations | ~10 (11%) |
| Persons with no citation of any kind | ~62 (67%) |

### By source

| Source | Persons citing it (via LifeEvent) |
|--------|----------------------------------|
| Farnham (2002) | 15 — the primary authority for the poet's direct line |
| Descendant report (2009) | 12 — primary for the Byfield–Minnesota branch |
| Find A Grave | 3 — death/burial confirmations |
| ME Historical Society | 4 — Portland residences and civic roles |

### By confidence

| Level | Count | Notes |
|-------|-------|-------|
| `confirmed` | 18 | Multiple sources or primary documents |
| `probable` | 7 | Single reliable published source |
| `uncertain` | 0 | — |
| `conflicting` | 0 | — |
| `uncited` | 68 | Present in seed data, source inferable from the descendant report but no formal LifeEvent linking |

---

## Known gaps and recommendations

1. **Bulk uncited persons (68/93).** Most uncited individuals appear in the
   descendant report (2009) which is the seed script's primary source. Adding
   LifeEvent entries for birth and death facts would formalize citations that
   are currently implicit. The data is already in the Person records; only the
   `tree.add_event(LifeEvent(...))` wiring is missing.

2. **Poet's children (generation 6).** Charles, Ernest, Fanny, Alice, Edith,
   and Anne Allegra Longfellow are well-documented public figures but have no
   LifeEvent citations. Wikipedia, the National Park Service (Longfellow
   House–Washington's Headquarters NHS), and Farnham (2002) would all support
   these facts.

3. **Find A Grave memorial IDs.** Three persons cite Find A Grave memorials in
   their notes text (Memorial #22571205, #14327894, #101663338) but only as
   free-text strings. Promoting these to structured source references would
   make them machine-auditable.

4. **Date precision.** Several early dates use the dual-dating convention
   (e.g., "1650/51", "1739/40") reflecting the Julian-to-Gregorian calendar
   transition. The seed script stores only one form. This is documented here
   for transparency, not as an error.

5. **Spouse records.** Many spouses (Abigail Thompson, Patience Young, Hepsibah
   Plumer, etc.) have no birth/death dates and no formal source citation. They
   appear in the descendant report as contextual mentions rather than
   independently documented individuals.

---

## How to cite new facts

When adding data to the seed script or through the app's editing UI:

1. **Identify the source** — use an existing `Source` id or create a new one.
2. **Add a LifeEvent** with the `source=` parameter pointing to the source id.
3. **Set confidence** — use `Confidence.CONFIRMED` for multi-source or primary
   documents; `PROBABLE` for single reliable sources; `UNCERTAIN` for
   inferences.
4. **Update this file** — add the person/fact to the appropriate generation
   table with its source basis and status.

For the app's Citation model (`src/models/citation.py`), the same principles
apply: every citation should reference a source id, specify which entity field
it supports, and carry a confidence level.
