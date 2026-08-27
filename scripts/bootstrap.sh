#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

mkdir -p data/runtime
python -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -e ".[dev]"
jobflow init-db
echo ""
echo "Ready. Start API with:"
echo "  source .venv/bin/activate && uvicorn jobflow.api.main:app --reload"
echo ""
echo "Optional PostgreSQL: docker compose up -d db  (then set DATABASE_URL in .env)"
