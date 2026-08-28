# Testing

This project has two test suites — Python (pytest) and JavaScript (vitest) — both
run in CI on every push to `main` and `task/**` branches.

## Running Tests

```bash
# Python tests
pip install pytest
pytest tests/ -x -q

# JavaScript tests
npm ci
npm test          # runs vitest via package.json "test" script

# Both (what CI does)
pytest tests/ -x -q && npm test
```

## Python Tests (pytest)

### Configuration

Pytest is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

`pythonpath = ["src"]` means imports in tests resolve from `src/` — write
`from models.person import Person`, not `from src.models.person import Person`.

### Test files

Python tests live in `tests/` and cover models (`test_tree`, `test_relationships`,
`test_dates`, `test_timeline`), database operations (`test_database`,
`test_db_transaction`, `test_sources`), import/export (`test_gedcom`,
`test_json_io`), HTTP endpoints (`test_web_people_crud`, `test_web_relative_crud`,
`test_web_uploads`, `test_sources_api`), auth (`test_auth_hardening`,
`test_login_gate`, `test_editor_access_control`), storage (`test_storage`),
and misc (`test_undo`, `test_geocoder`, `test_articles`, `test_cli`,
`test_relationship_validation`). A fixture GEDCOM file lives at
`tests/fixtures/tiny.ged`.

### Fixtures and test data

There is no shared `conftest.py` — each file defines its own fixtures.

**Database fixture** (model/repository tests):

```python
@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def repo(db_path):
    return TreeRepository(db_path)
```

**Flask test client** (HTTP endpoint tests): monkeypatch `FAMILY_TREE_DB`, then
`importlib.reload(web_server)` so Flask picks up the new env var. See
`test_web_people_crud.py` for the full pattern — it yields
`(client, repo, tmp_path)`.

**Factory functions**: most test classes define `_make_person(**overrides)` with
sensible defaults you can selectively override.

**3-generation family**: `test_tree.py`, `test_relationships.py`,
`test_timeline.py`, and `test_undo.py` each build the same synthetic family
(IDs: `al`, `beth`, `carl`, `dana`, `eve`, `fay`, `gus`) via
`_build_test_tree()`.

**Auth helpers**: `_sign_in()` / `_sign_in_as()` inject session data via
`client.session_transaction()`.

**Mocking**: most tests use real SQLite and Flask's test client. Only boto3
(S3Storage) is mocked. Env vars are set via `monkeypatch`.

### Adding a new Python test

1. Create `tests/test_yourmodule.py`.
2. Copy the `db_path`/`repo` fixtures from `test_database.py`, or the
   `app_client` fixture from `test_web_people_crud.py` for HTTP tests.
3. Build test data with model classes (`Person`, `Relationship`, etc.).
4. Assert with plain `assert`. Run: `pytest tests/test_yourmodule.py -x -v`.

## JavaScript Tests (vitest)

### Configuration

```js
// vitest.config.js
export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/js/setup.js"],
  },
});
```

The setup file stubs `window.matchMedia` and provides a `d3` proxy so modules
that reference D3 at parse time don't crash in jsdom.

### File layout

```
tests/js/
├── setup.js               # jsdom stubs: matchMedia, d3 proxy
├── a11y.test.js           # Accessibility: lang, skip links, ARIA roles, form labels
├── edit-form-date.test.js # EditForm structured date input (year → month → day)
├── on-this-day.test.js    # "On this day" card: date filtering, event sorting
├── pure-logic.test.js     # Search ranking, fog distance, lane assignment, butterfly layout
├── research-queue.test.js # Gap detection: missing fields, death date logic
└── state-refresh.test.js  # Post-mutation refresh order (loadData → lanes → views)
```

### Import pattern

Tests import directly from `web/js/` source files:

```js
import { buildButterflyLayout } from "../../web/js/04-tree.js";
import { S } from "../../web/js/00-state.js";
```

### Common patterns

```js
describe("feature", () => {
  beforeEach(() => {
    S.PEOPLE_MAP = {};
    document.body.innerHTML = "";
  });

  it("does the thing", () => {
    expect(result).toBe(expected);
  });
});
```

Factory helpers like `makePerson(id, given, surname, opts)` create test data
with defaults. DOM events are fired with:

```js
el.dispatchEvent(new Event("input", { bubbles: true }));
```

### Adding a new JS test

1. Create `tests/js/yourfeature.test.js`.
2. Import the functions you want to test from `web/js/`.
3. If your module reads global state, reset `S.*` fields in `beforeEach`.
4. If your module touches the DOM, clear `document.body.innerHTML` in `beforeEach`.
5. If your module calls D3 rendering functions, test the pure logic paths only —
   D3 is stubbed as a no-op and won't produce real SVG.
6. Run with `npx vitest run tests/js/yourfeature.test.js`.

## CI Pipeline

CI runs four parallel jobs (see `.github/workflows/ci.yml`):

| Job | What it checks |
|-----|---------------|
| **lint** | `ruff check`, `ruff format --check`, `mypy` |
| **test** | `pytest tests/ -x -q` |
| **js-unit** | `npm test` (vitest) |
| **smoke** | Headless Chromium: seeds DB, starts Flask, validates page globals and tab rendering |

The smoke test (`scripts/smoke_test.mjs`) starts the Flask server on port 8137,
loads the page with Playwright, and checks that key functions exist on `window`,
data loads, the tree SVG renders, and all five tabs (tree, timeline, map, photos,
relationships) produce visible content.

## Linting

```bash
ruff check src/ tests/        # lint
ruff format --check src/ tests/  # format check
ruff format src/ tests/        # auto-format
mypy                           # type check (configured in pyproject.toml)
```

Ruff is configured in `pyproject.toml` with rules E, W, F, I, UP, B enabled and
line length of 100 (E501 not enforced).
