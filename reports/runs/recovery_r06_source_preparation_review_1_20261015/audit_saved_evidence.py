"""Independently verify frozen public evidence without network or database access."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as element_tree
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from ai_intel.ingestion.parsing.parsers import parse_html_document
from ai_intel.ingestion.parsing.pdf_text import parse_pdf_text_layer

WORKTREE = Path("D:/wt/r06-prep-review")
REVIEW_RUN = Path(__file__).resolve().parent
AUTHOR_RUN = WORKTREE / "reports/runs/recovery_r06_source_preparation_20261015"
COMMIT = "e4f20b0bf74ec8781bd1e5cede96daa6341c101d"
BASELINE = "23c18784d71f1ed788072e6b3f2af70bac94fcb1"


def git_bytes(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(WORKTREE), *arguments],
        check=True,
        capture_output=True,
    ).stdout


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def valid_time(value: str) -> datetime:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00", value)
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(hours=8)
    return parsed


def main() -> int:
    assert git_bytes("rev-parse", "HEAD").decode().strip() == COMMIT
    scope = git_bytes("diff", "--name-only", BASELINE, COMMIT).decode().splitlines()
    assert len(scope) == 117
    assert all(
        path.startswith("reports/runs/recovery_r06_source_preparation_20261015/")
        or path
        in {
            "docs/design/recovery/r06_source_matrix_draft.md",
            "reports/tasks/R06-source-preparation.md",
        }
        for path in scope
    )
    commands = [
        json.loads(line)
        for line in (AUTHOR_RUN / "commands.jsonl").read_text().splitlines()
    ]
    assert len(commands) == 36
    for command in commands:
        assert valid_time(command["ended_at"]) >= valid_time(command["started_at"])
        for stream in ("stdout", "stderr"):
            path = AUTHOR_RUN / command[stream]
            expected = command[f"{stream}_sha256"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
            blob = git_bytes(
                "show", f"{COMMIT}:{path.relative_to(WORKTREE).as_posix()}"
            )
            assert hashlib.sha256(blob).hexdigest() == expected
    blocked = read_json(AUTHOR_RUN / "public_get_summary.json")
    received = read_json(AUTHOR_RUN / "doh_public_get_summary.json")
    assert isinstance(blocked, list) and isinstance(received, list)
    assert len(blocked) == len(received) == 8
    batch_pairs = (
        ("public_get_batch", blocked, "system"),
        ("public_get_doh_batch", received, "cloudflare_doh"),
    )
    batch_results = []
    for label, attempts, resolver in batch_pairs:
        command = next(item for item in commands if item["label"] == label)
        assert command["command_argv"][0].endswith("/Scripts/python.exe")
        assert command["cwd"].startswith("C:/Users/yinha/.codex/worktrees/r06-src/")
        recorded_stdout = [
            json.loads(line)
            for line in (AUTHOR_RUN / command["stdout"]).read_text().splitlines()
        ]
        assert recorded_stdout == attempts
        command_start = valid_time(command["started_at"])
        command_end = valid_time(command["ended_at"])
        for attempt in attempts:
            assert (
                read_json(AUTHOR_RUN / f"{attempt['label']}.metadata.json") == attempt
            )
            assert attempt["dns_resolver"] == resolver
            assert attempt["method"] == "GET" and attempt["attempts"] == 1
            assert attempt["max_response_bytes"] == 2097152
            assert attempt["total_timeout_seconds"] == 15
            assert attempt["redirect_hops_allowed"] == 0
            assert (
                attempt["credentials_used"] is False
                and attempt["is_synthetic"] is False
            )
            assert attempt["mode"] == "real_gateway_public_readonly"
            start = valid_time(attempt["started_at"])
            end = valid_time(attempt["ended_at"])
            assert command_start <= start <= end <= command_end
            assert 0 <= attempt["elapsed_seconds"] <= 15
            assert abs((end - start).total_seconds() - attempt["elapsed_seconds"]) <= 1
            if resolver == "system":
                assert attempt["status_code"] is None
                assert attempt["body_path"] is None and attempt["body_sha256"] is None
                assert attempt["redacted_headers"] is None
                assert attempt["response_size_bytes"] is None
                assert attempt["error_type"] == "NetworkPolicyViolation"
                assert attempt["error_code"] == "network_policy_violation"
                assert (
                    attempt["error_message"]
                    == "resolved address is private or local (DNS rebinding)"
                )
                assert not (AUTHOR_RUN / f"{attempt['label']}.body").exists()
            else:
                assert attempt["status_code"] == 200
                request_url = urlsplit(attempt["request_url"])
                final_url = urlsplit(attempt["final_url"])
                assert (request_url.scheme, request_url.netloc, request_url.path) == (
                    final_url.scheme,
                    final_url.netloc,
                    final_url.path,
                )
                assert parse_qsl(request_url.query) == parse_qsl(final_url.query)
                body_path = AUTHOR_RUN / attempt["body_path"]
                body = body_path.read_bytes()
                assert len(body) == attempt["response_size_bytes"] <= 2097152
                assert hashlib.sha256(body).hexdigest() == attempt["body_sha256"]
                assert (
                    hashlib.sha256(attempt["request_url"].encode()).hexdigest()
                    == attempt["request_fingerprint_sha256"]
                )
                blob = git_bytes(
                    "show", f"{COMMIT}:{body_path.relative_to(WORKTREE).as_posix()}"
                )
                assert blob == body
                for header, value in attempt["redacted_headers"].items():
                    if header.casefold() in {"authorization", "cookie", "set-cookie"}:
                        assert value == "REDACTED"
        batch_results.append(
            {
                "label": label,
                "resolver": resolver,
                "windows_python": command["command_argv"][0],
                "cwd": command["cwd"],
                "started_at": command["started_at"],
                "ended_at": command["ended_at"],
                "script_exit": command["exit_code"],
                "attempt_count": len(attempts),
            }
        )
    for first, second in zip(blocked, received, strict=True):
        assert first["request_url"] == second["request_url"]
    osv = read_json(AUTHOR_RUN / "doh_01_osv_ollama.body")
    assert osv["id"] == "GHSA-fccc-8m69-8r78" and osv["schema_version"] == "1.9.0"
    assert osv["affected"][0]["package"]["ecosystem"] == "Go"
    assert osv["affected"][0]["package"]["name"] == "github.com/ollama/ollama"
    vendor = read_json(AUTHOR_RUN / "doh_02_vllm_vendor.body")[0]
    assert vendor["ghsa_id"] == "GHSA-6cxc-2vcg-w5qc"
    assert vendor["html_url"].startswith(
        "https://github.com/vllm-project/vllm/security/advisories/"
    )
    assert vendor["state"] == "published"
    avid = read_json(AUTHOR_RUN / "doh_03_avid_community.body")
    assert [(item["path"], item["type"]) for item in avid] == [
        ("vulnerabilities/2022", "dir"),
        ("vulnerabilities/2023", "dir"),
    ]
    release = read_json(AUTHOR_RUN / "doh_04_ollama_release.body")[0]
    assert release["id"] == 413093320 and release["tag_name"] == "v0.40.5-rc0"
    assert release["target_commitish"] == "main" and release["prerelease"] is True
    feed = element_tree.fromstring(
        (AUTHOR_RUN / "doh_05_trailofbits_feed.body").read_bytes()
    )
    entries = feed.findall("./channel/item")
    assert len(entries) == 20
    assert parsedate_to_datetime(
        entries[0].findtext("pubDate")
    ).utcoffset() == timedelta(hours=-4)
    ai_titles = [
        entry.findtext("title")
        for entry in entries
        if re.search(
            r"\b(AI|agent|LLM)\b", entry.findtext("title") or "", re.IGNORECASE
        )
    ]
    assert ai_titles
    namespaces = {
        "a": "http://www.w3.org/2005/Atom",
        "o": "http://a9.com/-/spec/opensearch/1.1/",
    }
    atom = element_tree.fromstring(
        (AUTHOR_RUN / "doh_06_arxiv_ai_security.body").read_bytes()
    )
    papers = atom.findall("a:entry", namespaces)
    assert [paper.findtext("a:id", namespaces=namespaces) for paper in papers] == [
        "http://arxiv.org/abs/2609.05903v2",
        "http://arxiv.org/abs/2610.19452v1",
    ]
    assert atom.findtext("o:totalResults", namespaces=namespaces) == "1065"
    assert (
        papers[0].findtext("a:published", namespaces=namespaces)
        == "2026-09-05T05:56:41Z"
    )
    assert (
        papers[0].findtext("a:updated", namespaces=namespaces) == "2026-10-14T08:52:25Z"
    )
    nist = parse_pdf_text_layer((AUTHOR_RUN / "doh_07_nist_ai_rmf.body").read_bytes())
    assert nist.status == "parsed" and len(nist.blocks) == 48
    voluntary_pages = [
        block.page_number for block in nist.blocks if "voluntary" in block.text.lower()
    ]
    assert voluntary_pages and "NIST AI 100-1" in nist.normalized_text
    cac_raw = (AUTHOR_RUN / "doh_08_cac_generative_ai.body").read_bytes()
    cac = parse_html_document(cac_raw)
    assert all(
        value in cac.normalized_text
        for value in ("第15号", "2023年7月10日", "2023年8月15日")
    )
    assert "2023年07月13日 15:00" in cac_raw.decode("utf-8")
    matrix = (WORKTREE / "docs/design/recovery/r06_source_matrix_draft.md").read_text(
        encoding="utf-8"
    )
    categories = (
        "structured_vulnerability",
        "vendor_advisory",
        "security_community",
        "code_repository",
        "technical_blog",
        "academic_paper",
        "technical_standard",
        "policy_regulation",
    )
    matrix_rows = [
        line
        for line in matrix.splitlines()
        if line.startswith(tuple(f"| {category} |" for category in categories))
    ]
    assert len(matrix_rows) == 8 and all(
        len(row.split("|")) == 12 for row in matrix_rows
    )
    assert "D AVID / U huntr" in matrix_rows[2]
    invalid_uuid_files = []
    for source in sorted((WORKTREE / "config/sources").glob("*.yaml")):
        identity = re.search(
            r'source_id: "([^"]+)"', source.read_text(encoding="utf-8")
        ).group(1)
        try:
            UUID(identity)
        except ValueError:
            invalid_uuid_files.append(source.name)
    assert invalid_uuid_files == [
        "policies.yaml",
        "repository.yaml",
        "standards.yaml",
        "vendor.yaml",
    ]
    junit_counts = {}
    for label, count in (
        ("baseline_source_contracts", 31),
        ("t08_security_contracts", 8),
    ):
        suite = element_tree.parse(REVIEW_RUN / f"{label}.xml").getroot()[0]
        assert int(suite.attrib["tests"]) == count
        assert all(
            suite.attrib[key] == "0" for key in ("failures", "errors", "skipped")
        )
        junit_counts[label] = {
            key: int(suite.attrib[key])
            for key in ("tests", "failures", "errors", "skipped")
        }
    result = {
        "reviewed_commit": COMMIT,
        "reviewed_tree": git_bytes("rev-parse", "HEAD^{tree}").decode().strip(),
        "allowed_changed_paths": len(scope),
        "author_commands_verified": len(commands),
        "committed_stream_blobs_verified": len(commands) * 2,
        "committed_source_bodies_verified": len(received),
        "body_total_bytes": sum(row["response_size_bytes"] for row in received),
        "source_attempts": len(blocked) + len(received),
        "batches": batch_results,
        "http200_records": [
            {
                key: row[key]
                for key in (
                    "label",
                    "started_at",
                    "ended_at",
                    "response_size_bytes",
                    "elapsed_seconds",
                    "body_sha256",
                )
            }
            for row in received
        ],
        "ai_blog_titles": ai_titles,
        "nist_voluntary_physical_pages": voluntary_pages,
        "nist_normalized_sha256": hashlib.sha256(
            nist.normalized_text.encode()
        ).hexdigest(),
        "cac_date_precision": "calendar_date; webpage clock timezone unspecified",
        "invalid_example_uuid_files": invalid_uuid_files,
        "junit_counts": junit_counts,
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "network_requests": 0,
        "database_writes": 0,
        "result": "independent_saved_evidence_passed",
    }
    (REVIEW_RUN / "independent_evidence.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
