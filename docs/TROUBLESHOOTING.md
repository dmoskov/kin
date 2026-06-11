# Troubleshooting

Common issues encountered in local development, CI, and production — with their
fixes.

## Local Development

### App won't start: "SECRET_KEY must be set in production"

**Cause:** `DATABASE_URL` is set in your environment, which puts the app in
production mode — and production mode requires `SECRET_KEY`.

**Fix:** Either unset `DATABASE_URL` to use local SQLite (the default), or set
`SECRET_KEY`:

```bash
# Option A: use SQLite (no DATABASE_URL needed)
unset DATABASE_URL
python3 -m cli serve

# Option B: set a key for local Postgres
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
python3 -m cli serve
```

### Wrong database: changes don't appear / empty tree after restart

**Cause:** Without `FAMILY_TREE_DB` set, the app writes to `data/family.db`
relative to the working directory. If you start the app from different
directories, each gets its own database file.

**Fix:** Always set `FAMILY_TREE_DB` to an absolute path:

```bash
export FAMILY_TREE_DB="$HOME/kin/private/data/family.db"
```

### Import errors: "ModuleNotFoundError: No module named 'models'"

**Cause:** `src/` is not on the Python path.

**Fix:** Either install the package in editable mode or set `PYTHONPATH`:

```bash
pip install -e .          # editable install (recommended)
# or
PYTHONPATH=src pytest      # one-off for running tests
```

### Pre-commit hook blocks commit: "possible PII detected"

The PII guard (`.githooks/pre-commit`) scans for real email addresses, birth
dates in `data/`, and AWS instance IDs. Move personal data to `private/`
(gitignored) and use `example.com` addresses in code. Enable the hook with
`git config core.hooksPath .githooks`.

### Optional features not working

| Feature | Required env var | Notes |
|---------|-----------------|-------|
| Google Sign-In | `GOOGLE_CLIENT_ID` | Without it, the app runs in open access mode |
| AI document parsing | `ANTHROPIC_API_KEY` | Gracefully disabled if unset (returns 503) |

### Photo uploads rejected (413 error)

File exceeds `MAX_PHOTO_BYTES` (default 8 MB) or `MAX_DOC_BYTES` (50 MB).
Increase via env var. In production, also check nginx `client_max_body_size`.

### Photos or documents not persisting

Create the private directory structure: `mkdir -p private/{data,photos,documents,config}`.
Docker users: ensure `./private/` is mounted as a volume.

## Tests

### pytest: "ModuleNotFoundError" on import

Run pytest from the repo root (where `pyproject.toml` lives) so it picks up
`pythonpath = ["src"]`, or `pip install -e .`.

### pytest: stale module state between tests

Flask reads config at import time. Web test fixtures must
`importlib.reload(web_server)` after monkeypatching env vars. See the
`app_client` fixture pattern in [TESTING.md](TESTING.md).

### vitest: "ReferenceError: d3 is not defined"

Check that `vitest.config.js` has `setupFiles: ["./tests/js/setup.js"]`. If
a new module references D3 at the top level, use optional chaining
(`d3?.select?.(...)`) or guard with `typeof d3 !== "undefined"`.

### vitest: "TypeError: ... is not a function" on DOM APIs

jsdom doesn't implement every browser API. Add a stub to `tests/js/setup.js`
following the existing `matchMedia` pattern.

## CI

### Lint job fails: ruff format

**Cause:** Code isn't formatted to ruff's style.

**Fix:**

```bash
ruff format src/ tests/
ruff check src/ tests/ --fix
```

Then commit the reformatted files.

### Lint job fails: mypy

**Cause:** Type errors in `src/`.

**Fix:** Run `mypy` locally (configured in `pyproject.toml`):

```bash
mypy
```

Common fixes: add type annotations, fix import paths, add `# type: ignore` for
third-party stubs not available.

### Smoke test times out

The Flask server must start within 60 seconds. Check that `scripts/build_js.sh`
succeeds, `data/seed_longfellow.py` runs without error, and
`web_server.init_db()` completes.

### Smoke test fails: "missing function global"

`scripts/smoke_test.mjs` asserts eight functions on `window`: `renderTree`,
`renderTimeline`, `renderMap`, `showPersonPanel`, `checkAuth`, `openLightbox`,
`switchTab`, `computeRelationship`. If you renamed one, update the smoke test.
If a JS module fails to parse, check the browser console in the CI log.

### Auto-merge skipped: merge conflict

**Cause:** The `auto-merge.yml` workflow only merges `task/**` branches that
apply cleanly to `main`. If your branch conflicts, it's left for manual
resolution.

**Fix:**

```bash
git fetch origin main
git rebase origin/main
# resolve conflicts
git push --force-with-lease
```

## Production / Deployment

### Deploy fails: "DEPLOY_HOST or DEPLOY_SSH_KEY secret not set"

The deploy workflow requires both as GitHub repo secrets. Add them in
Settings → Secrets → Actions.

### Health check fails after deploy

The deploy script polls `/healthz` 10 times (3s apart) after restarting the
systemd service. If it doesn't come up in 30s:

1. `ssh ec2-user@<host>`
2. `sudo systemctl status familytree` and `sudo journalctl -u familytree -n 50`
3. Common causes: missing `.env`, bad `DATABASE_URL`, port 8000 in use.

### Backups not running

1. `systemctl status familytree-backup.timer`
2. `journalctl -u familytree-backup.service -n 20`
3. Verify `.env` has `DATABASE_URL` and `BACKUP_S3_BUCKET`, and the IAM role
   has `s3:PutObject` / `s3:DeleteObject`. See [deploy/BACKUPS.md](../deploy/BACKUPS.md).

### Database: "relation does not exist" (PostgreSQL)

Schema migrations haven't run. The app auto-applies them via `init_db()` on
startup — restart the service (`sudo systemctl restart familytree`). If it
persists, check `schema_version` table vs `src/database/schema.py`.

### SQLite: "database is locked"

SQLite allows one writer at a time. Use PostgreSQL (`DATABASE_URL`) for
production. The single-threaded Flask dev server avoids this locally.

### nginx: 502 Bad Gateway

gunicorn isn't running on `127.0.0.1:8000`. Check:
`sudo systemctl status familytree` and `ss -tlnp | grep 8000`.

### Uploads fail in production (nginx 413)

Increase `client_max_body_size` in `deploy/nginx.conf` (`sudo nginx -t &&
sudo systemctl reload nginx`). Also check `MAX_DOC_BYTES` /
`MAX_PHOTO_BYTES` env vars.
