"""Inspect only the already-scanned rejected paths; never output matched values."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="milliseconds")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    started = now()
    tick = time.monotonic()
    (RUN / "rejection_metadata_started.json").write_text(
        json.dumps({"started_at": started, "command": sys.argv}), encoding="utf-8"
    )
    sys.path.insert(0, str(ROOT))
    from scripts import security_scan

    scanned = json.loads((RUN / "s2_child_receipt.json").read_text(encoding="utf-8"))
    rejected = [
        finding
        for finding in scanned["findings"]
        if finding["category"] not in security_scan.SAFE_CATEGORIES
    ]
    paths = sorted({finding["path"] for finding in rejected})
    assert len(rejected) == 25 and len(paths) == 13
    table = json.loads(
        (ROOT / "reports/security/recovery_fixture_false_positives.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(table["records"]) == 136
    results = []
    for relative_path in paths:
        path = security_scan._canonical_path(ROOT, relative_path)
        raw = path.read_bytes()
        raw_sha256 = digest(raw)
        normalized_raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        normalized_sha256 = digest(normalized_raw)
        crlf_sha256 = digest(normalized_raw.replace(b"\n", b"\r\n"))
        content = raw.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
        registered = [record for record in table["records"] if record["path"] == relative_path]
        registered_hashes = sorted({record["raw_sha256"] for record in registered})
        function_ranges = []
        if path.suffix == ".py":
            tree = ast.parse(content)
            function_ranges = [
                (node.lineno, node.end_lineno, node.name)
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
        json_strings = []
        if path.suffix == ".json":
            stack = [json.loads(content)]
            while stack:
                node = stack.pop()
                if isinstance(node, dict):
                    stack.extend(node.values())
                elif isinstance(node, list):
                    stack.extend(node)
                elif isinstance(node, str):
                    json_strings.append(node)
        matches = []
        for pattern_id, pattern in security_scan.PATTERNS.items():
            for match in pattern.finditer(content):
                matched_text = match.group(0)
                quote_start = min(index for index, char in enumerate(matched_text) if char in "\"'")
                value = matched_text[quote_start + 1 : -1]
                same_binding = [
                    record
                    for record in registered
                    if (
                        record["pattern_id"] == pattern_id
                        and record["start"] == match.start()
                        and record["end"] == match.end()
                        and record["match_value"] == value
                    )
                ]
                raw_match = any(record["raw_sha256"] == raw_sha256 for record in same_binding)
                line = content[: match.start()].count("\n") + 1
                public_comparison = (
                    pattern_id == "original_secret_value_pattern"
                    and path.suffix == ".py"
                    and value == "password authentication failed"
                    and security_scan.is_public_authentication_failure_comparison(content, line)
                )
                if (
                    raw_match
                    or public_comparison
                    or value in security_scan.DOCUMENTED_DEV_PLACEHOLDERS
                ):
                    continue
                matching_strings = [item for item in json_strings if matched_text in item]
                matches.append(
                    {
                        "pattern_id": pattern_id,
                        "line": line,
                        "start": match.start(),
                        "end": match.end(),
                        "match_value_sha256": digest(value.encode()),
                        "match_value_characters": len(value),
                        "registered_same_pattern_span_value": bool(same_binding),
                        "registered_same_binding_raw_sha_match": raw_match,
                        "registered_same_binding_hashes": sorted(
                            {record["raw_sha256"] for record in same_binding}
                        ),
                        "python_enclosing_test_functions": [
                            name
                            for first, last, name in function_ranges
                            if last is not None
                            and first <= line <= last
                            and name.startswith("test_")
                        ],
                        "json_string_occurrences": len(matching_strings),
                        "json_match_is_inside_pytest_nodeid": bool(matching_strings)
                        and all(".py::test_" in item for item in matching_strings),
                        "dsn_or_url_userinfo_shape": bool(
                            re.search(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/]+:[^\s/@]+@", value)
                        ),
                        "jwt_shape": bool(
                            re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", value)
                        ),
                        "opaque_urlsafe_value_shape": bool(
                            re.fullmatch(r"[A-Za-z0-9_-]{24,}", value)
                        ),
                        "actual_secret_status": (
                            "unverified_do_not_register_without_provenance_review"
                        ),
                    }
                )
        assert Counter(match["pattern_id"] for match in matches) == Counter(
            finding["pattern_id"] for finding in rejected if finding["path"] == relative_path
        )
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative_path],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        results.append(
            {
                "path": relative_path,
                "bytes": len(raw),
                "raw_sha256": raw_sha256,
                "normalized_lf_sha256": normalized_sha256,
                "normalized_crlf_sha256": crlf_sha256,
                "crlf_count": raw.count(b"\r\n"),
                "lone_lf_count": raw.count(b"\n") - raw.count(b"\r\n"),
                "lone_cr_count": raw.count(b"\r") - raw.count(b"\r\n"),
                "registered_record_count": len(registered),
                "registered_raw_sha256": registered_hashes,
                "registered_raw_sha_match": raw_sha256 in registered_hashes,
                "newline_only_lf_variant_registered": normalized_sha256 in registered_hashes,
                "newline_only_crlf_variant_registered": crlf_sha256 in registered_hashes,
                "git_tracked": tracked.returncode == 0,
                "rejected_matches": matches,
            }
        )
    assert sum(len(row["rejected_matches"]) for row in results) == 25
    receipt = {
        "started_at": started,
        "ended_at": now(),
        "duration_seconds": time.monotonic() - tick,
        "exit_code": 0,
        "mode": "offline_rejection_metadata_only",
        "scope": "13 paths already read by approved original S2 scan, registry 136 only",
        "head_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "rejected_path_count": len(results),
        "rejected_match_count": 25,
        "files": results,
        "no_exemptions_added": True,
        "no_matched_text_or_values_output": True,
        "actual_secret_values_not_injected": True,
    }
    (RUN / "rejected_findings_metadata.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in (
                    "started_at",
                    "ended_at",
                    "duration_seconds",
                    "exit_code",
                    "rejected_path_count",
                    "rejected_match_count",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
