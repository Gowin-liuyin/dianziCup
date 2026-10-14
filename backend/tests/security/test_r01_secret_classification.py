"""R01 的历史夹具分类必须精确，且真实秘密检测优先于分类。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from scripts.security_scan import (
    PATTERNS,
    ClassificationError,
    load_fixture_classifications,
    main,
    scan_repository,
)


def write_reviewed_fixture(repository_root: Path) -> tuple[Path, Path, str]:
    fixture_value = "fixture" + "-memory-csrf"
    source_path = repository_root / "reports/runs/fixture/original.log"
    source_path.parent.mkdir(parents=True)
    content = 'csrf_token: "' + fixture_value + '"\n'
    source_path.write_bytes(content.encode())
    records = []
    for pattern_id, pattern in PATTERNS.items():
        match = pattern.finditer(content).__next__()
        records.append(
            {
                "path": source_path.relative_to(repository_root).as_posix(),
                "raw_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                "pattern_id": pattern_id,
                "pattern_version": 1,
                "pattern_sha256": hashlib.sha256(pattern.pattern.encode()).hexdigest(),
                "start": match.start(),
                "end": match.end(),
                "match_value": fixture_value,
                "category": "verified_synthetic_fixture",
                "fixture_origin": {
                    "source_commit": "b" * 40,
                    "source_blob": "c" * 40,
                    "source_path": "frontend/tests/isolated.test.ts",
                    "source_line": 1,
                    "source_sha256": "d" * 64,
                    "data_mode": "fixture",
                },
                "review_ref": "reports/reviews/recovery/fixture-review.md",
            }
        )
    table_path = repository_root / "classifications.json"
    table_path.write_text(json.dumps({"schema_version": 1, "records": records}), encoding="utf-8")
    return source_path, table_path, fixture_value


def test_exact_reviewed_old_fixture_is_classified(tmp_path: Path) -> None:
    _, table_path, _ = write_reviewed_fixture(tmp_path)
    records = load_fixture_classifications(tmp_path, table_path)
    findings = scan_repository(tmp_path, records)
    assert len(findings) == 2
    assert {finding.category for finding in findings} == {"verified_synthetic_fixture"}


@pytest.mark.parametrize("mutation", ["unrelated_bytes", "same_line", "adjacent_line"])
def test_modified_original_log_is_rejected(tmp_path: Path, mutation: str) -> None:
    source_path, table_path, _ = write_reviewed_fixture(tmp_path)
    records = load_fixture_classifications(tmp_path, table_path)
    content = source_path.read_bytes()
    credential = b'api_key: "' + b"NewCredentialShape0123456789" + b'"'
    if mutation == "unrelated_bytes":
        content += b"changed evidence\n"
    elif mutation == "same_line":
        content = content.rstrip(b"\n") + b" " + credential + b"\n"
    else:
        content += credential + b"\n"
    source_path.write_bytes(content)
    findings = scan_repository(tmp_path, records)
    assert findings
    assert all(finding.category == "unclassified_credential_shape" for finding in findings)


def test_copying_synthetic_value_to_new_file_is_rejected(tmp_path: Path) -> None:
    source_path, table_path, _ = write_reviewed_fixture(tmp_path)
    copied_path = source_path.with_name("copied.log")
    copied_path.write_bytes(source_path.read_bytes())
    findings = scan_repository(tmp_path, load_fixture_classifications(tmp_path, table_path))
    copied_findings = [finding for finding in findings if finding.path.endswith("copied.log")]
    assert len(copied_findings) == 2
    assert all(finding.category == "unclassified_credential_shape" for finding in copied_findings)


def test_unlisted_span_is_rejected_even_when_file_hash_is_reviewed(tmp_path: Path) -> None:
    _, table_path, _ = write_reviewed_fixture(tmp_path)
    table = json.loads(table_path.read_text(encoding="utf-8"))
    table["records"][0]["start"] += 1
    table_path.write_text(json.dumps(table), encoding="utf-8")
    findings = scan_repository(tmp_path, load_fixture_classifications(tmp_path, table_path))
    assert any(finding.category == "unclassified_credential_shape" for finding in findings)


@pytest.mark.parametrize(
    "escaping_path",
    [
        "../outside.log",
        "/outside.log",
        "reports/../outside.log",
        "C:/old-wt/original.log",
        "reports\\runs\\fixture\\original.log",
        "backend/tests/original.log",
    ],
)
def test_classification_paths_cannot_escape_or_leave_allowed_roots(
    tmp_path: Path, escaping_path: str
) -> None:
    _, table_path, _ = write_reviewed_fixture(tmp_path)
    table = json.loads(table_path.read_text(encoding="utf-8"))
    table["records"][0]["path"] = escaping_path
    table_path.write_text(json.dumps(table), encoding="utf-8")
    with pytest.raises(ClassificationError, match="invalid_classification_path"):
        load_fixture_classifications(tmp_path, table_path)


def test_authorized_exact_secret_match_overrides_synthetic_classification(tmp_path: Path) -> None:
    _, table_path, fixture_value = write_reviewed_fixture(tmp_path)
    findings = scan_repository(
        tmp_path,
        load_fixture_classifications(tmp_path, table_path),
        exact_secret_values=(fixture_value,),
    )
    exact_findings = [finding for finding in findings if finding.category == "exact_secret_match"]
    assert len(exact_findings) == 1
    assert fixture_value not in repr(findings)


def test_unclassified_error_metadata_never_contains_credential_value(tmp_path: Path) -> None:
    source_path, _, fixture_value = write_reviewed_fixture(tmp_path)
    findings = scan_repository(tmp_path, ())
    assert all(finding.path == source_path.relative_to(tmp_path).as_posix() for finding in findings)
    assert all(finding.category == "unclassified_credential_shape" for finding in findings)
    assert fixture_value not in repr(findings)


@pytest.mark.parametrize(
    "relative_root", ["backend/src", "scripts", "frontend/src", "frontend/dist", "reports/runs"]
)
def test_every_original_scan_root_still_rejects_unknown_credentials(
    tmp_path: Path, relative_root: str
) -> None:
    source_path = tmp_path / relative_root / "unreviewed.js"
    source_path.parent.mkdir(parents=True)
    source_path.write_text('token: "' + "UnreviewedCredential0123456" + '"', encoding="utf-8")
    findings = scan_repository(tmp_path, ())
    assert len(findings) == 2
    assert all(finding.category == "unclassified_credential_shape" for finding in findings)


def test_cli_exact_input_has_priority_and_never_prints_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _, table_path, fixture_value = write_reviewed_fixture(tmp_path)
    cli_table_path = tmp_path / "reports/security/recovery_fixture_false_positives.json"
    cli_table_path.parent.mkdir(parents=True)
    cli_table_path.write_bytes(table_path.read_bytes())
    monkeypatch.setenv("DIANZI_SYNTHETIC_SECRET_PROBE", fixture_value)
    result = main(
        ["--repository-root", str(tmp_path), "--secret-env", "DIANZI_SYNTHETIC_SECRET_PROBE"]
    )
    output = capsys.readouterr().out
    assert result == 1
    assert fixture_value not in output
    assert json.loads(output)["exact_scan"] == "completed"


def test_cli_missing_authorized_input_cannot_claim_completed_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DIANZI_SYNTHETIC_SECRET_PROBE", raising=False)
    result = main(
        ["--repository-root", str(tmp_path), "--secret-env", "DIANZI_SYNTHETIC_SECRET_PROBE"]
    )
    assert result == 2
    assert json.loads(capsys.readouterr().out)["exact_scan"] == "not_run"


def test_empty_exact_secret_input_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ClassificationError, match="invalid_exact_secret_input"):
        scan_repository(tmp_path, (), exact_secret_values=("",))


@pytest.mark.parametrize("valid_review_sha", [True, False])
def test_review_fixture_provenance_requires_a_fixed_report_hash(
    tmp_path: Path, valid_review_sha: bool
) -> None:
    _, table_path, _ = write_reviewed_fixture(tmp_path)
    table = json.loads(table_path.read_text(encoding="utf-8"))
    for record in table["records"]:
        record["fixture_origin"] = {
            "source_type": "review_fixture",
            "source_path": "reports/runs/fixture/original.log",
            "source_sha256": record["raw_sha256"],
            "source_line": 1,
            "data_mode": "fixture",
            "review_report_path": "reports/reviews/fixture-review.md",
            "review_report_sha256": "e" * 64 if valid_review_sha else "unfixed",
            "review_candidate_commit": "f" * 40,
        }
    table_path.write_text(json.dumps(table), encoding="utf-8")
    if valid_review_sha:
        findings = scan_repository(tmp_path, load_fixture_classifications(tmp_path, table_path))
        assert all(finding.category == "verified_synthetic_fixture" for finding in findings)
    else:
        with pytest.raises(ClassificationError, match="invalid_classification_record"):
            load_fixture_classifications(tmp_path, table_path)


@pytest.mark.parametrize("field", ["pattern_version", "pattern_sha256", "data_mode"])
def test_classification_pattern_and_fixture_provenance_are_validated(
    tmp_path: Path, field: str
) -> None:
    _, table_path, _ = write_reviewed_fixture(tmp_path)
    table = json.loads(table_path.read_text(encoding="utf-8"))
    if field == "data_mode":
        table["records"][0]["fixture_origin"][field] = "live"
    else:
        table["records"][0][field] = 2 if field == "pattern_version" else "e" * 64
    table_path.write_text(json.dumps(table), encoding="utf-8")
    with pytest.raises(ClassificationError, match="invalid_classification_record"):
        load_fixture_classifications(tmp_path, table_path)
