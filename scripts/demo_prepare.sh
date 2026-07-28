#!/usr/bin/env bash
# One-command demo prep: build stack, wait for health, seed 12/12 scenarios.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Starting Docker Compose stack …"
docker compose up --build -d

echo "==> Waiting for API health …"
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "    API healthy after ${i} attempt(s)."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: API did not become healthy within 30 attempts."
    exit 1
  fi
  sleep 2
done

echo "==> Seeding 12 mandatory + 2 supplementary scenarios …"
docker exec gnani-emi-api python scripts/seed_scenarios.py --base-url http://localhost:8000

echo ""
echo "Demo ready."
echo "  Dashboard : http://localhost:8000/"
echo "  Swagger   : http://localhost:8000/docs"
echo "  Health    : http://localhost:8000/health"
echo "  Demo guide: docs/DEMO.md"
echo ""
curl -s http://localhost:8000/health | python -m json.tool 2>/dev/null || curl -s http://localhost:8000/health
