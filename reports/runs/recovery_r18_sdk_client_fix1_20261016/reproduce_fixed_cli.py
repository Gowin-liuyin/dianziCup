"""Save exact ASCII/UTF-8 subprocess bytes using the unchanged review fixture inputs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from test_cli_fix1_regressions import INTERNATIONAL_COMPONENT, STACK
from test_independent_boundaries import (
    ANSWER,
    QUESTION,
    SYNTHETIC_KEY,
    TASK,
    fixture_server,
    run_cli,
)

RUN = Path(__file__).resolve().parent


if __name__ == "__main__":
    cases = []
    for encoding in ("ascii", "utf-8"):
        for name, command, status, request, response in (
            ("answer", "ask", 200, QUESTION, ANSWER),
            ("queued", "ask", 202, QUESTION, TASK),
            ("stack", "check", 200, {"components": [INTERNATIONAL_COMPONENT]}, STACK),
        ):
            label = encoding + "_" + name
            with fixture_server(status, json.dumps(response).encode("utf-8")) as (base, calls):
                result = run_cli(base, command, request, encoding=encoding)
            assert result.returncode == 2 and json.loads(result.stdout) == response
            assert len(calls) == 1 and result.stdout.isascii()
            assert b"Traceback" not in result.stderr
            assert SYNTHETIC_KEY.encode() not in result.stdout + result.stderr
            for stream, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
                path = RUN / f"fixed_cli_{label}_{stream}.raw"
                assert not path.exists()
                path.write_bytes(raw)
            cases.append(
                {
                    "case": label,
                    "exit_code": result.returncode,
                    "stdout_size_bytes": len(result.stdout),
                    "complete_json": True,
                    "loopback_calls": len(calls),
                }
            )
    receipt = {
        "observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "source_sha": "6d85742b0114cc5e304e88b2aa930755ccce9bc9",
        "fixture_only": True,
        "cases": cases,
    }
    (RUN / "fixed_cli_raw_observations.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt))
