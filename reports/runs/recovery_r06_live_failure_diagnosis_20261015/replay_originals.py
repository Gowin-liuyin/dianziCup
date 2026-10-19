"""Replay saved official bytes without network, credentials, or source text output."""

import ast
import hashlib
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.ingestion.catalog_pages import normalize_catalog_page, normalize_avid_blob, select_avid_blob

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
SOURCE = ROOT / "backend/src"


def current_time():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def static_messages():
    messages = set()
    for path in SOURCE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                if node.exc.args and isinstance(node.exc.args[0], ast.Constant):
                    value = node.exc.args[0].value
                    if isinstance(value, str):
                        messages.add(value)
    return messages


def failure_summary(error, safe_messages):
    message = str(error)
    return {
        "exception_type": type(error).__name__,
        "exception_message": message if message in safe_messages else "<nonstatic message withheld>",
        "exception_message_sha256": hashlib.sha256(message.encode()).hexdigest(),
        "source_frames": [
            {"path": str(Path(frame.filename).relative_to(ROOT)), "line": frame.lineno,
             "function": frame.name}
            for frame in traceback.extract_tb(error.__traceback__)
            if Path(frame.filename).is_relative_to(SOURCE)
        ],
    }


def main():
    started_at = current_time()
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    safe_messages = static_messages()
    results = []
    for entry in manifest:
        original_path = Path(entry["original_path"])
        body = original_path.read_bytes()
        row = {"label": entry["label"], "original_path": str(original_path),
               "sha256": hashlib.sha256(body).hexdigest(), "size_bytes": len(body),
               "source_kind": entry["source_kind"], "cursor": entry.get("cursor", {})}
        try:
            if entry["source_kind"] == "avid_community":
                tree_body = Path(entry["tree_path"]).read_bytes()
                selected = select_avid_blob(tree_body, entry.get("cursor", {}))
                if selected is None:
                    raise AssertionError("expected selected AVID blob")
                document = normalize_avid_blob(selected, body)
                row.update({"verdict": "normalized", "documents": 1,
                            "selected_blob_sha": selected.blob_sha,
                            "selected_tree_sha": selected.tree_sha,
                            "selected_path": selected.path,
                            "next_cursor": selected.next_cursor,
                            "normalized_sha256": hashlib.sha256(document.payload).hexdigest()})
            else:
                page = normalize_catalog_page(entry["source_kind"], body,
                                              entry.get("cursor", {}), entry.get("headers", {}))
                row.update({"verdict": "normalized", "documents": len(page.documents),
                            "next_cursor": page.next_cursor})
        except Exception as error:
            row.update({"verdict": "failed", **failure_summary(error, safe_messages)})
        results.append(row)
    output = {"source_sha": "1156b2ed6616e3a4297215c2893d2cbe633f5215",
              "argv": sys.argv, "cwd": os.getcwd(), "started_at": started_at,
              "finished_at": current_time(), "runtime_executable": sys.executable,
              "network_requests": 0, "database_calls": 0, "results": results}
    exit_code = 1 if any(row["verdict"] == "failed" for row in results) else 0
    output["exit_code"] = exit_code
    (RUN / (sys.argv[2] + ".json")).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
