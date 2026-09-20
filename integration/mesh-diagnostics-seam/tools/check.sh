#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python -m pytest tests tests_reference -q
bun run check
bun run test
bun run build
