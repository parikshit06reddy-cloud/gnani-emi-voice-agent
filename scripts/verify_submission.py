#!/usr/bin/env python3
"""Verify assignment §11 submission artifacts are present in the repository.

Exits 0 when every required path exists, 1 otherwise. Safe to run in CI
without a running server or external credentials.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Assignment §11 submission requirements → repo paths (relative to root).
REQUIRED_PATHS: list[tuple[str, Path]] = [
    ("1. Source code", PROJECT_ROOT / "app" / "main.py"),
    ("2. Gnani bot configuration export", PROJECT_ROOT / "gnani_config" / "agent-config.json"),
    ("3. Bot prompt and conversation flow", PROJECT_ROOT / "prompts" / "01-system-prompt.md"),
    ("4. FastAPI application", PROJECT_ROOT / "app" / "main.py"),
    ("5. Dummy dashboard", PROJECT_ROOT / "app" / "static" / "index.html"),
    ("6. Database schema", PROJECT_ROOT / "docs" / "database-schema.md"),
    ("7. Postman collection", PROJECT_ROOT / "postman"),
    ("8. .env.example", PROJECT_ROOT / ".env.example"),
    ("9. Dockerfile", PROJECT_ROOT / "Dockerfile"),
    ("10. docker-compose.yml", PROJECT_ROOT / "docker-compose.yml"),
    ("11. README", PROJECT_ROOT / "README.md"),
    ("12. Architecture diagram", PROJECT_ROOT / "docs" / "architecture-diagram.png"),
    ("13. Sample call recordings", PROJECT_ROOT / "samples" / "recordings"),
    ("14. Sample webhook payloads", PROJECT_ROOT / "samples" / "webhooks"),
    ("15. Dashboard screenshots", PROJECT_ROOT / "docs" / "screenshots" / "dashboard-list.png"),
    ("16. Stage-code logic doc", PROJECT_ROOT / "docs" / "stage-code-logic.md"),
    ("17. Test results", PROJECT_ROOT / "docs" / "test-scenarios.md"),
]

# Strongly recommended for a polished submission (warn, do not fail).
RECOMMENDED_PATHS: list[tuple[str, Path]] = [
    ("CI workflow", PROJECT_ROOT / ".github" / "workflows" / "ci.yml"),
    ("Demo guide", PROJECT_ROOT / "docs" / "DEMO.md"),
    ("Live call runbook", PROJECT_ROOT / "docs" / "live-call-runbook.md"),
    ("Console findings", PROJECT_ROOT / "gnani_config" / "CONSOLE_FINDINGS.md"),
    ("Architecture write-up", PROJECT_ROOT / "docs" / "architecture.md"),
]


def _check(label: str, path: Path) -> bool:
    if path.exists():
        print(f"  OK  {label}: {path.relative_to(PROJECT_ROOT)}")
        return True
    print(f"  MISSING  {label}: {path.relative_to(PROJECT_ROOT)}")
    return False


def main() -> int:
    print("Checking assignment §11 submission artifacts …\n")
    missing = 0
    for label, path in REQUIRED_PATHS:
        if not _check(label, path):
            missing += 1

    print("\nRecommended artifacts …")
    for label, path in RECOMMENDED_PATHS:
        _check(label, path)

    if missing:
        print(f"\nFAIL: {missing} required artifact(s) missing.")
        return 1

    print("\nPASS: all required submission artifacts present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
