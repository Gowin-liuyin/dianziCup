"""Exact registrations never exempt changed files, copies, or authorized secret bytes."""

from __future__ import annotations

import hashlib
import json
import shutil
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from scripts.security_scan import load_fixture_classifications, scan_repository

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "reports/runs/recovery_r20_secret_provenance_20261016"
TABLE = ROOT / "reports/security/recovery_fixture_false_positives.json"
BUNDLE = ROOT / "fixtures/synthetic/security/r20_secret_provenance_20261016.zip"
EXTENSION_RUN = ROOT / "reports/runs/batch21_r20_registry_extension_20261024"
EXTENSION_BUNDLE = ROOT / "fixtures/synthetic/security/r20_registry_extension_batch21.zip"
PROPOSAL = json.loads((RUN / "registration_proposal.json").read_text(encoding="utf-8"))
EXTENSION = json.loads((EXTENSION_RUN / "registration_proposal.json").read_text(encoding="utf-8"))
REGISTRATIONS = (PROPOSAL, EXTENSION)
for _registration in REGISTRATIONS:
    for _row in _registration["proposals"]:
        _row["registration"] = _registration
ROWS = [*PROPOSAL["proposals"], *EXTENSION["proposals"]]
PATHS = sorted({row["path"] for row in ROWS})
UNIQUE_VALUES = list({row["value_sha256"]: row for row in ROWS}.values())


def registration_for(relative_path: str) -> dict[str, object]:
    """Return the registration whose fixture bundle and bindings cover the path."""
    for registration in REGISTRATIONS:
        if relative_path in registration["fixture_bindings"]:
            return registration
    raise AssertionError(f"no registration binds {relative_path}")


def isolated_copy(tmp_path: Path, relative_path: str, row: dict[str, object] | None = None) -> Path:
    registration = row["registration"] if row is not None else registration_for(relative_path)
    bundle_path = ROOT / str(registration["fixture_bundle"]["path"])
    source = tmp_path / relative_path
    source.parent.mkdir(parents=True, exist_ok=True)
    binding = registration["fixture_bindings"][relative_path]
    digest = binding["raw_sha256"]
    assert isinstance(digest, str) and len(digest) == 64
    archive_bytes = bundle_path.read_bytes()
    assert hashlib.sha256(archive_bytes).hexdigest() == registration["fixture_bundle"]["raw_sha256"]
    with ZipFile(BytesIO(archive_bytes)) as archive:
        raw = archive.read(digest + ".bin")
    assert hashlib.sha256(raw).hexdigest() == digest
    if row is not None and hashlib.sha256(raw).hexdigest() != row["raw_sha256"]:
        assert row["raw_variant"] == "original_physical"
        assert b"\r" not in raw
        raw = raw.replace(b"\n", b"\r\n")
    if row is not None:
        assert hashlib.sha256(raw).hexdigest() == row["raw_sha256"]
    source.write_bytes(raw)
    return source


def test_original_registry_bytes_and_all_54_records_are_preserved() -> None:
    original = (RUN / "registry_original_bytes.bin").read_bytes()
    assert hashlib.sha256(original).hexdigest() == PROPOSAL["original_registry_sha256"]
    old_records = json.loads(original)["records"]
    current = json.loads(TABLE.read_text(encoding="utf-8"))["records"]
    assert len(old_records) == 54
    assert current[:54] == old_records
    assert len(current) == PROPOSAL["total_records"] + EXTENSION["new_records"]
    assert current[PROPOSAL["total_records"] :] == EXTENSION["table_records"]


@pytest.mark.parametrize(
    "row", ROWS, ids=lambda row: f"{row['pattern_id']}:{row['path']}:{row['line']}"
)
def test_only_frozen_candidate_files_receive_exact_classifications(
    tmp_path: Path, row: dict[str, object]
) -> None:
    path = str(row["path"])
    source = isolated_copy(tmp_path, path, row)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == row["raw_sha256"]
    classifications = load_fixture_classifications(tmp_path, TABLE)
    findings = scan_repository(tmp_path, classifications)
    matching = [finding for finding in findings if finding.pattern_id == row["pattern_id"]]
    assert matching
    assert all(finding.category == "verified_synthetic_fixture" for finding in matching)


@pytest.mark.parametrize("path", PATHS)
def test_changes_to_any_registered_file_revoke_its_classification(
    tmp_path: Path, path: str
) -> None:
    source = isolated_copy(tmp_path, path)
    source.write_bytes(source.read_bytes() + b"\nchanged provenance control\n")
    findings = scan_repository(tmp_path, load_fixture_classifications(tmp_path, TABLE))
    assert findings
    assert all(finding.category == "unclassified_credential_shape" for finding in findings)


@pytest.mark.parametrize("path", PATHS)
def test_copying_any_registered_artifact_does_not_copy_its_exemption(
    tmp_path: Path, path: str
) -> None:
    source = isolated_copy(tmp_path, path)
    copied = source.with_name("unreviewed-copy" + source.suffix)
    shutil.copyfile(source, copied)
    findings = scan_repository(tmp_path, load_fixture_classifications(tmp_path, TABLE))
    copied_findings = [finding for finding in findings if finding.path.endswith(copied.name)]
    assert copied_findings
    assert all(finding.category == "unclassified_credential_shape" for finding in copied_findings)


@pytest.mark.parametrize("row", UNIQUE_VALUES, ids=lambda row: str(row["value_sha256"])[:12])
def test_exact_authorized_secret_bytes_override_every_registered_value_family(
    tmp_path: Path, row: dict[str, object]
) -> None:
    path = str(row["path"])
    source = isolated_copy(tmp_path, path, row)
    raw = source.read_bytes()
    content = raw.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    start, end = row["start"], row["end"]
    assert isinstance(start, int) and isinstance(end, int)
    matched = content[start:end]
    quote = min(index for index, char in enumerate(matched) if char in "\"'")
    value = matched[quote + 1 : -1]
    assert hashlib.sha256(value.encode()).hexdigest() == row["value_sha256"]
    exact_value = value if value.encode() in raw else value.replace("\n", "\r\n")
    assert exact_value.encode() in raw
    findings = scan_repository(
        tmp_path, load_fixture_classifications(tmp_path, TABLE), (exact_value,)
    )
    exact = [finding for finding in findings if finding.category == "exact_secret_match"]
    assert len(exact) == 1
    assert value not in repr(findings)


@pytest.mark.parametrize("path", PATHS)
def test_new_credential_shape_in_a_registered_file_remains_rejected(
    tmp_path: Path, path: str
) -> None:
    source = isolated_copy(tmp_path, path)
    token_value = "Synthetic" + "UnregisteredControl123456"
    source.write_bytes(source.read_bytes() + ('\ntoken: "' + token_value + '"\n').encode())
    findings = scan_repository(tmp_path, load_fixture_classifications(tmp_path, TABLE))
    assert findings
    assert all(finding.category == "unclassified_credential_shape" for finding in findings)
    assert token_value not in repr(findings)


@pytest.mark.parametrize("path", [path for path in PATHS if path.startswith("frontend/")])
def test_mixed_line_endings_are_not_an_approved_variant(tmp_path: Path, path: str) -> None:
    source = isolated_copy(tmp_path, path)
    raw = source.read_bytes()
    mixed = raw.replace(b"\r\n", b"\n", 1) if b"\r\n" in raw else raw.replace(b"\n", b"\r\n", 1)
    source.write_bytes(mixed)
    findings = scan_repository(tmp_path, load_fixture_classifications(tmp_path, TABLE))
    assert findings
    assert all(finding.category == "unclassified_credential_shape" for finding in findings)
