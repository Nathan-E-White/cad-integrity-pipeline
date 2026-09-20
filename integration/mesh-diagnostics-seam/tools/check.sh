#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python -m pytest -q
node tools/compile_svelte.mjs
cd frontend
node --experimental-strip-types --test test/*.test.ts
if command -v bun >/dev/null 2>&1; then
  bun run check
  bun run build
else
  npm run check
  npm run build
fi
