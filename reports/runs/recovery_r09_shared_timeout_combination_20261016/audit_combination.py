"""Audit the frozen combination, original bytes, and real fixture test receipts."""

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as element_tree
from pathlib import Path

from ai_intel.enrichment import card_extraction, knowledge_cards
from ai_intel.infrastructure.models import generation

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BASE = "ed217564e9cf3571b430d0fe7caa4d3999c7320b"
COMBINATION = "dd36cf78c3d15138683d09c12ea867c0055b9674"
AUTHOR = Path("C:/Users/yinha/.codex/worktrees/r09-knowledge-cards/dianzi")
REVIEWER = Path("C:/Users/yinha/.codex/worktrees/r09-knowledge-cards-review-1/dianzi")
AUTHOR_RUN = "reports/runs/recovery_r09_knowledge_cards_20261016"
REVIEW_RUN = "reports/runs/recovery_r09_knowledge_cards_review_1_20261016"
CHANGED_CODE = (
    "backend/src/ai_intel/infrastructure/models/generation.py",
    "backend/tests/unit/test_r05_generation_predispatch_timeout.py",
)
PROBE_HASH = "76ca4d4064f65bfd08846a6e57a2c4fde087a10d6422d563094b412890058bbf"


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def write_json(name: str, value: object) -> None:
    (RUN / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def audit_manifest(owner: Path, relative_run: str) -> dict[str, object]:
    """Check manifest bodies and retain raw-versus-Git distinctions."""
    relative_path = f"{relative_run}/artifact_manifest.json"
    body = (owner / relative_path).read_bytes()
    sidecar = (owner / relative_run / "artifact_manifest.sha256").read_text().split()[0]
    assert digest(body) == sidecar
    manifest = json.loads(body)
    records = []
    for item in manifest["files"]:
        relative = item["path"]
        raw = (owner / relative).read_bytes()
        record = {"path": relative, "raw_sha256": digest(raw), "expected_sha256": item["sha256"]}
        if owner == AUTHOR:
            frozen = git("show", f"{BASE}:{relative}")
            combination_raw = (ROOT / relative).read_bytes()
            assert raw.replace(b"\r\n", b"\n") == combination_raw.replace(b"\r\n", b"\n")
            assert frozen == git("show", f"{COMBINATION}:{relative}")
            record["base_git_sha256"] = digest(frozen)
            record["combination_raw_sha256"] = digest(combination_raw)
            assert item["sha256"] in {digest(raw), digest(frozen)}
            record["combination_raw_identical"] = raw == combination_raw
            record["line_endings_only_if_raw_differs"] = True
            record["combination_git_identical"] = True
        else:
            assert item["sha256"] == digest(raw)
        records.append(record)
    result = {"path": str(owner / relative_path), "raw_sha256": digest(body), "files": records}
    if owner == AUTHOR:
        assert body == (ROOT / relative_path).read_bytes()
        assert (owner / relative_run / "artifact_manifest.sha256").read_bytes() == (
            ROOT / relative_run / "artifact_manifest.sha256"
        ).read_bytes()
        result["base_git_sha256"] = digest(git("show", f"{BASE}:{relative_path}"))
    return result


def main() -> None:
    """Fail if code scope, source origins, frozen bytes, or counts differ."""
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", COMBINATION, "HEAD"], cwd=ROOT, check=True
    )
    material_changes = git("diff", "--name-only", COMBINATION, "HEAD").decode().splitlines()
    for relative in material_changes:
        assert (
            relative == ".gitattributes"
            or relative == "reports/tasks/R09-shared-timeout-combination.md"
            or relative.startswith(RUN.relative_to(ROOT).as_posix() + "/")
        )
    changed = git("diff", "--name-only", BASE, COMBINATION).decode().splitlines()
    assert sorted(changed) == sorted(CHANGED_CODE)
    for relative in CHANGED_CODE:
        assert git("show", f"{COMBINATION}:{relative}") == git(
            "show", f"47c47bc2b5d537166ee47a01c2ab14c035466e3d:{relative}"
        )
    provenance = {"executable": sys.executable, "prefix": sys.prefix}
    assert Path(sys.prefix).resolve() == (ROOT / "backend/.venv").resolve()
    for module in (generation, card_extraction, knowledge_cards):
        source = Path(module.__file__).resolve()
        assert source.is_relative_to((ROOT / "backend/src").resolve())
        provenance[module.__name__] = str(source)
    original_probe = (REVIEWER / REVIEW_RUN / "test_independent_boundaries.py").read_bytes()
    assert digest(original_probe) == PROBE_HASH
    assert original_probe == (RUN / "test_independent_boundaries.py").read_bytes()
    command_records = []
    case_sets = {}
    for path in sorted(RUN.glob("*.command.json")):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["label"] = path.name.removesuffix(".command.json")
        junit = RUN / f"{receipt['label']}.xml"
        if junit.exists():
            suites = element_tree.parse(junit).getroot()
            cases = suites.findall(".//testcase")
            case_sets[receipt["label"]] = {
                (case.get("classname"), case.get("name")) for case in cases
            }
            receipt["junit"] = {
                "tests": len(cases),
                "failures": len(suites.findall(".//failure")),
                "errors": len(suites.findall(".//error")),
                "skipped": len(suites.findall(".//skipped")),
            }
        command_records.append(receipt)
    assert len(case_sets["baseline_independent_17"]) == 17
    assert len(case_sets["combination_independent_17"]) == 17
    regression = set().union(
        case_sets["unit_regression_268"],
        case_sets["contract_regression_76"],
        case_sets["security_regression_36"],
    )
    assert len(regression) == 380
    assert case_sets["focused_66"].issubset(regression)
    assert case_sets["original_t22_6"].issubset(regression)
    scope = {
        "base_sha": BASE,
        "combination_code_sha": COMBINATION,
        "combination_code_tree": git("rev-parse", f"{COMBINATION}^{{tree}}").decode().strip(),
        "changed_code": changed,
        "code_files": [
            {
                "path": relative,
                "git_sha256": digest(git("show", f"{COMBINATION}:{relative}")),
                "raw_sha256": digest((ROOT / relative).read_bytes()),
            }
            for relative in CHANGED_CODE
        ],
        "provenance": provenance,
        "original_probe_sha256": PROBE_HASH,
        "author_material": audit_manifest(AUTHOR, AUTHOR_RUN),
        "reviewer_material": audit_manifest(REVIEWER, REVIEW_RUN),
        "unique_related_regression_tests": len(regression),
        "external_requests": 0,
        "real_model_calls": 0,
        "pg_sessions": 0,
    }
    write_json("scope_audit.json", scope)
    write_json("command_index.json", command_records)
    print(
        json.dumps(
            {
                "scope_verified": True,
                "regression_tests": len(regression),
                "original_probe_sha256": PROBE_HASH,
            }
        )
    )


if __name__ == "__main__":
    main()
