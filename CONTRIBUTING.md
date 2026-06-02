# Contributing to Family Tree

Thanks for your interest in improving Family Tree! This guide covers how to get
set up, the conventions the project follows, and what to expect when you open a
pull request.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you agree to uphold it.

## Privacy first

This is genealogy software, so **never commit real personal data.** All personal
family information lives in a `private/` directory that is gitignored. A
`pre-commit` hook in `.githooks/` blocks real email addresses and personal seed
scripts from being committed — enable it after cloning:

```bash
git config core.hooksPath .githooks
```

When you need sample data for a test or a demo, use the public-domain
`data/seed_longfellow.py` or the synthetic `data/example_family.json`. Tests must
use synthetic data only.

## Development setup

```bash
git clone https://github.com/dmoskov/family-tree.git
cd family-tree
git config core.hooksPath .githooks            # enable the PII guard

# Python backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Frontend tooling
npm install
```

Run the app locally:

```bash
python3 -m cli serve   # http://localhost:8000
```

## Tests and checks

Please run the full suite before opening a PR — CI (`.github/workflows/ci.yml`)
runs the same checks:

```bash
ruff check .            # Python lint
mypy                    # Python type check
pytest                  # Python tests
npm test                # JS unit tests (vitest)
```

Frontend JS is bundled with esbuild. If you change files under `web/js/`,
rebuild the bundle:

```bash
bash scripts/build_js.sh
```

## Pull requests

1. Fork the repo and create a branch off `main` (`feature/...` or `fix/...`).
2. Keep changes focused — one logical change per PR.
3. Add or update tests for any behavior change.
4. Make sure lint, type checks, and tests all pass.
5. Write a clear PR description explaining the what and why.

## Coding conventions

- **Python:** follow the existing style; `ruff` and `mypy` are the source of
  truth. Fail loudly with clear error messages rather than swallowing errors.
- **JavaScript:** vanilla ES modules under `web/js/`, loaded in order by
  `index.html`. Match the patterns in neighboring files.
- Prefer editing existing files over adding new ones, and reuse existing
  utilities rather than reimplementing them.

## Reporting bugs and requesting features

Open an issue describing the problem or proposal. For bugs, include steps to
reproduce, what you expected, and what actually happened. **Do not include real
family data** in issues — reproduce with synthetic data instead.

Thanks for contributing!
