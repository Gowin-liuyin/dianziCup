"""按原 T06 模式扫描，只有已审查的精确历史夹具匹配可以分类。"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

PATTERNS = {
    "original_secret_pattern": re.compile(
        r"(api[_-]?key|secret[_-]?key|db[_-]?pass|secret|token|password)"
        r"\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
        re.IGNORECASE,
    ),
    "original_secret_value_pattern": re.compile(
        r"(api[_-]?key|secret[_-]?key|db[_-]?pass|secret|password|passwd|token|jwt)"
        r"\s*[:=]\s*['\"]([^'\"]{6,})['\"]",
        re.IGNORECASE,
    ),
}
SCAN_ROOTS = ("backend/src", "scripts", "frontend/src", "frontend/dist", "reports/runs")
SCAN_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".log", ".json", ".html"}
DOCUMENTED_DEV_PLACEHOLDERS = {"dev-only-not-a-secret", "Dev-Only-Not-A-Secret-1!"}
SAFE_CATEGORIES = {
    "verified_synthetic_fixture",
    "documented_dev_placeholder",
    "public_failure_comparison",
}


class ClassificationError(ValueError):
    """分类表格式或路径不满足受控的精确匹配合同。"""


@dataclass(frozen=True)
class FixtureClassification:
    path: str
    raw_sha256: str
    pattern_id: str
    start: int
    end: int
    match_value: str


@dataclass(frozen=True)
class ScanFinding:
    path: str
    pattern_id: str
    category: str


def _is_canonical_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    return (
        "\\" not in value
        and ":" not in value
        and not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in value.split("/"))
        and path.as_posix() == value
    )


def _canonical_path(repository_root: Path, relative_path: str) -> Path:
    if not _is_canonical_relative_path(relative_path):
        raise ClassificationError("invalid_classification_path")
    root = repository_root.resolve()
    target = (root / relative_path).resolve()
    allowed_roots = tuple((root / scan_root).resolve() for scan_root in SCAN_ROOTS)
    if not target.is_relative_to(root) or not any(
        target.is_relative_to(scan_root) for scan_root in allowed_roots
    ):
        raise ClassificationError("invalid_classification_path")
    return target


def _has_hex(value: object, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def _has_valid_fixture_origin(origin: object) -> bool:
    if (
        not isinstance(origin, dict)
        or origin.get("data_mode") != "fixture"
        or not _has_hex(origin.get("source_sha256"), 64)
        or not _is_canonical_relative_path(origin.get("source_path"))
        or type(origin.get("source_line")) is not int
        or origin["source_line"] < 1
    ):
        return False
    if origin.get("source_type", "git") == "git":
        return _has_hex(origin.get("source_commit"), 40) and _has_hex(origin.get("source_blob"), 40)
    return (
        origin.get("source_type") == "review_fixture"
        and origin["source_path"].startswith("reports/runs/")
        and _has_hex(origin.get("review_candidate_commit"), 40)
        and _has_hex(origin.get("review_report_sha256"), 64)
        and _is_canonical_relative_path(origin.get("review_report_path"))
        and origin["review_report_path"].startswith("reports/reviews/")
    )


def _record_from_json(repository_root: Path, record: object) -> FixtureClassification:
    if not isinstance(record, dict):
        raise ClassificationError("invalid_classification_record")
    relative_path = record.get("path")
    if not isinstance(relative_path, str):
        raise ClassificationError("invalid_classification_path")
    _canonical_path(repository_root, relative_path)
    pattern_id = record.get("pattern_id")
    pattern = PATTERNS.get(pattern_id) if isinstance(pattern_id, str) else None
    start, end = record.get("start"), record.get("end")
    match_value = record.get("match_value")
    origin = record.get("fixture_origin")
    review_ref = record.get("review_ref")
    raw_sha256 = record.get("raw_sha256")
    if (
        not _has_hex(raw_sha256, 64)
        or not isinstance(pattern_id, str)
        or pattern is None
        or type(record.get("pattern_version")) is not int
        or record.get("pattern_version") != 1
        or record.get("pattern_sha256") != hashlib.sha256(pattern.pattern.encode()).hexdigest()
        or type(start) is not int
        or type(end) is not int
        or start < 0
        or end <= start
        or not isinstance(match_value, str)
        or not match_value
        or record.get("category") != "verified_synthetic_fixture"
        or not _has_valid_fixture_origin(origin)
        or not isinstance(review_ref, str)
        or not review_ref.startswith("reports/reviews/")
    ):
        raise ClassificationError("invalid_classification_record")
    assert isinstance(raw_sha256, str)
    return FixtureClassification(relative_path, raw_sha256, pattern_id, start, end, match_value)


def load_fixture_classifications(
    repository_root: Path, table_path: Path
) -> tuple[FixtureClassification, ...]:
    """校验分类表；旧工作树绝对路径不能获得豁免。"""
    try:
        table: object = json.loads(table_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ClassificationError("invalid_classification_table") from error
    if (
        not isinstance(table, dict)
        or type(table.get("schema_version")) is not int
        or table.get("schema_version") != 1
        or not isinstance(table.get("records"), list)
    ):
        raise ClassificationError("invalid_classification_table")
    return tuple(_record_from_json(repository_root, record) for record in table["records"])


def is_public_authentication_failure_comparison(content: str, source_line: int) -> bool:
    """公开 PG 错误文案作为布尔比较不是密码赋值；直接字面量凭据仍拒绝。"""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or node.lineno != source_line:
            continue
        value = node.value
        if (
            isinstance(value, ast.Compare)
            and isinstance(value.left, ast.Constant)
            and value.left.value == "password authentication failed"
            and len(value.ops) == 1
            and isinstance(value.ops[0], ast.In)
        ):
            return True
    return False


def scan_repository(
    repository_root: Path,
    classifications: Sequence[FixtureClassification],
    exact_secret_values: Sequence[str] = (),
) -> list[ScanFinding]:
    """保留原根和扩展名；真实秘密按原始字节检测，先于任何正则分类。"""
    if any(not value for value in exact_secret_values):
        raise ClassificationError("invalid_exact_secret_input")
    reviewed_matches = set(classifications)
    findings = []
    for relative_root in SCAN_ROOTS:
        source_root = repository_root / relative_root
        if not source_root.exists():
            continue
        for source_path in sorted(source_root.rglob("*")):
            if not source_path.is_file() or source_path.suffix not in SCAN_SUFFIXES:
                continue
            relative_path = source_path.relative_to(repository_root).as_posix()
            try:
                checked_path = _canonical_path(repository_root, relative_path)
            except ClassificationError:
                findings.append(ScanFinding(relative_path, "path_boundary", "invalid_scan_path"))
                continue
            raw_content = checked_path.read_bytes()
            if any(value.encode() in raw_content for value in exact_secret_values):
                findings.append(
                    ScanFinding(relative_path, "authorized_exact", "exact_secret_match")
                )
            raw_sha256 = hashlib.sha256(raw_content).hexdigest()
            content = raw_content.decode("utf-8", errors="ignore").replace("\r\n", "\n")
            content = content.replace("\r", "\n")
            for pattern_id, pattern in PATTERNS.items():
                for match in pattern.finditer(content):
                    matched_text = match.group(0)
                    quote_start = min(
                        index for index, character in enumerate(matched_text) if character in "\"'"
                    )
                    matched_value = matched_text[quote_start + 1 : -1]
                    classification = FixtureClassification(
                        relative_path,
                        raw_sha256,
                        pattern_id,
                        match.start(),
                        match.end(),
                        matched_value,
                    )
                    category = "unclassified_credential_shape"
                    if classification in reviewed_matches:
                        category = "verified_synthetic_fixture"
                    elif pattern_id == "original_secret_value_pattern":
                        if matched_value in DOCUMENTED_DEV_PLACEHOLDERS:
                            category = "documented_dev_placeholder"
                        elif (
                            source_path.suffix == ".py"
                            and matched_value == "password authentication failed"
                            and is_public_authentication_failure_comparison(
                                content, content[: match.start()].count("\n") + 1
                            )
                        ):
                            category = "public_failure_comparison"
                    findings.append(ScanFinding(relative_path, pattern_id, category))
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    """只输出路径、模式、安全类别；未注入的实际秘密扫描明确未运行。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--secret-env", action="append", default=[])
    args = parser.parse_args(argv)
    root = args.repository_root.resolve()
    secret_values = []
    for name in args.secret_env:
        value = os.environ.get(name)
        if not value:
            print(json.dumps({"error": "authorized_secret_input_missing", "exact_scan": "not_run"}))
            return 2
        secret_values.append(value)
    try:
        classifications = load_fixture_classifications(
            root, root / "reports/security/recovery_fixture_false_positives.json"
        )
        findings = scan_repository(root, classifications, secret_values)
    except (ClassificationError, OSError):
        print(json.dumps({"error": "scan_input_invalid", "exact_scan": "not_run"}))
        return 2
    rejected = [finding for finding in findings if finding.category not in SAFE_CATEGORIES]
    print(
        json.dumps(
            {
                "exact_scan": "completed" if secret_values else "not_run",
                "findings": [asdict(finding) for finding in findings],
            }
        )
    )
    return 1 if rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
