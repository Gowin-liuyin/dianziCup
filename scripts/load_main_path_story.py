"""Operator command for the fixture main-path story. Does not print secrets."""

from __future__ import annotations

import os
import sys


def main() -> int:
    """Load the story only when DATA_MODE=fixture. A missing password is refused."""
    try:
        from ai_intel.fixtures.main_path_story import (
            FixtureModeRequired,
            StoryIncomplete,
            load_main_path_story,
            require_fixture_mode,
        )
        from ai_intel.infrastructure.content_storage_factory import build_content_storage
        from ai_intel.infrastructure.database import build_engine
        from ai_intel.infrastructure.settings import ConfigurationError, load_application_settings
    except ImportError as import_error:
        print(f"ERROR run inside backend venv: {import_error}", file=sys.stderr)
        return 2
    try:
        settings = load_application_settings()
        require_fixture_mode(settings.data_mode)
    except ConfigurationError as failure:
        print(f"ERROR {failure}", file=sys.stderr)
        return 2
    except FixtureModeRequired as failure:
        print(f"ERROR {failure}", file=sys.stderr)
        return 2
    password = os.environ.get("ADMIN_USER_PASSWORD", "")
    if not password:
        print("ERROR ADMIN_USER_PASSWORD is required and is not printed", file=sys.stderr)
        return 2
    if settings.database_url is None:
        print("ERROR valid DATABASE_URL environment configuration is required", file=sys.stderr)
        return 2
    engine = None
    try:
        engine = build_engine(settings)
        story = load_main_path_story(
            engine,
            build_content_storage(settings),
            data_mode=settings.data_mode,
            analyst_password=password,
        )
    except (FixtureModeRequired, StoryIncomplete, ValueError) as failure:
        print(f"ERROR {failure}", file=sys.stderr)
        return 1
    except Exception as failure:
        print(f"ERROR story load failed: {type(failure).__name__}", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    sys.stdout.write("\n".join(story.public_lines()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
