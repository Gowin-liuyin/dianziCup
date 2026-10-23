"""Run migrate and the fixture story against the temporary database. Prints no secrets."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\dianzi")
ENV_FILE = ROOT / "reports" / "runs" / "story_fixture_20261023" / "pg.env"
RAW = ROOT / "reports" / "runs" / "story_fixture_20261023" / "raw"
RESULT = ROOT / "reports" / "runs" / "story_fixture_20261023" / "story-result.txt"


def read_password() -> str:
    values = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        values[key] = value
    password = values["POSTGRES_PASSWORD"]
    if not password:
        raise RuntimeError("temporary database password is empty")
    return password


def run(script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "python", str(ROOT / "scripts" / script)],
        cwd=ROOT / "backend",
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def main() -> int:
    password = read_password()
    RAW.mkdir(parents=True, exist_ok=True)
    database_url = f"postgresql://story:{password}@127.0.0.1:25499/story_fixture"
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": database_url,
            "DATA_MODE": "fixture",
            "APP_ENV": "development",
            "ADMIN_USER_PASSWORD": password,
            "RAW_CONTENT_DIRECTORY": str(RAW),
            "CONTENT_STORE_BACKEND": "local",
        }
    )
    lines = []
    migrate = run("migrate.py", env)
    lines.append(f"migrate_exit={migrate.returncode}")
    lines.append("migrate_stdout=" + migrate.stdout.strip())
    lines.append("migrate_stderr=" + migrate.stderr.strip())
    if migrate.returncode != 0:
        RESULT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return migrate.returncode
    story = run("load_main_path_story.py", env)
    lines.append(f"story_exit={story.returncode}")
    lines.append("story_stdout=" + story.stdout.strip())
    lines.append("story_stderr=" + story.stderr.strip())
    RESULT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return story.returncode


if __name__ == "__main__":
    sys.exit(main())
