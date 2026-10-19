"""Independent review command recorder; no production mutation or remote IO."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
CLOCK_ZONE = timezone(timedelta(hours=8))


def main() -> None:
    name, cwd, *command = sys.argv[1:]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend" / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    started = datetime.now(CLOCK_ZONE).isoformat()
    with (OUTPUT / f"{name}.stdout.log").open("wb") as stdout:
        with (OUTPUT / f"{name}.stderr.log").open("wb") as stderr:
            completed = subprocess.run(
                command, cwd=cwd, env=env, stdout=stdout, stderr=stderr, timeout=180
            )
    receipt = {
        "command": command,
        "cwd": cwd,
        "started_at": started,
        "ended_at": datetime.now(CLOCK_ZONE).isoformat(),
        "exit_code": completed.returncode,
        "code_sha": "64dcd946601cd0e0f7435f59019ee709e3738a35",
        "material_sha": "37e492b4e26fc5b6197b60d2494926d4181a21c3",
        "environment_overrides": {"PYTHONPATH": env["PYTHONPATH"], "PYTHONIOENCODING": "utf-8"},
        "data_mode": "explicit isolated review fixtures; no remote IO",
    }
    xml_path = OUTPUT / f"{name}.xml"
    if xml_path.exists():
        suites = ElementTree.parse(xml_path).getroot().iter("testsuite")
        receipt["tests"] = [
            {key: suite.attrib.get(key) for key in ("name", "tests", "failures", "errors", "skipped")}
            for suite in suites
        ]
    (OUTPUT / f"{name}.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    sys.exit(completed.returncode)


if __name__ == "__main__":
    main()
