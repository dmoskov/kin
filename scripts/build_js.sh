#!/usr/bin/env bash
# Build the production JS bundle: bundle + minify the ES modules in web/js/
# into a single web/dist/app.min.js. The Flask index route serves this bundle
# when it exists (otherwise it serves the raw modules for development).
#
# Requires Node/npx (esbuild is fetched on demand). Run from anywhere.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p web/dist
npx --yes esbuild web/js/99-main.js \
  --bundle --minify --format=esm \
  --outfile=web/dist/app.min.js

echo "Built web/dist/app.min.js ($(wc -c < web/dist/app.min.js) bytes)"
