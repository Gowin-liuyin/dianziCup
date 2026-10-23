"""Apply PostgreSQL migrations to the current head. Does not print the database URL.

Run from the backend environment: ``uv run python ../scripts/migrate.py``.
``DATABASE_URL`` must already be in the environment. This script does not read a ``.env`` file.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Upgrade the configured database to head, or refuse when the URL is absent."""
    try:
        from ai_intel.infrastructure.database import run_migrations
        from ai_intel.infrastructure.settings import ConfigurationError, load_application_settings
    except ImportError as import_error:
        print(f"ERROR run inside backend venv: {import_error}", file=sys.stderr)
        return 2
    try:
        settings = load_application_settings()
    except ConfigurationError as failure:
        print(f"ERROR {failure}", file=sys.stderr)
        return 2
    if settings.database_url is None:
        print("ERROR valid DATABASE_URL environment configuration is required", file=sys.stderr)
        return 2
    try:
        run_migrations(settings.database_url.get_secret_value())
    except Exception as failure:
        print(f"ERROR migration failed: {type(failure).__name__}", file=sys.stderr)
        return 1
    print("migrations applied to head")
    return 0


if __name__ == "__main__":
    sys.exit(main())
