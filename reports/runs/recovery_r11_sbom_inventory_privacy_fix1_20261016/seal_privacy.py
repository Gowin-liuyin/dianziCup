"""核固定代码/原probe/raw材料，实际报告写入到秒；不读账号/模型配置或改进度。"""

import gzip
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
CODE = "6942c65efd5df013c077275cbb6d8cfec3585080"
BASE = "c0369e6b7cb71c19f7594da8737e6bb3717893f3"
REPORT = ROOT / "reports/tasks/R11-sbom-inventory-privacy-fix1.md"
REVIEW_RUN = Path(
    "D:/wt/r11-sbom-inventory-review1/reports/runs/recovery_r11_sbom_inventory_review1_20261016"
)
FIX1_REVIEW_RUN = Path(
    "D:/wt/r11-sbom-inventory-review1-fix1/reports/runs/"
    "recovery_r11_sbom_inventory_review1_fix1_20261016"
)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git(*arguments: str) -> bytes:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    start = datetime.now(ZoneInfo("Asia/Shanghai"))
    changes = git("diff", BASE, CODE, "--name-only").decode().splitlines()
    sources = []
    for path in changes:
        raw = (ROOT / path).read_bytes()
        blob = git("show", f"{CODE}:{path}")
        assert raw.replace(b"\r\n", b"\n") == blob
        sources.append(
            {
                "path": path,
                "raw_sha256": sha(raw),
                "git_lf_sha256": sha(blob),
                "git_blob": git("rev-parse", f"{CODE}:{path}").decode().strip(),
            }
        )
    unchanged = [
        "sbom_parser.py",
        "manifest_parser.py",
        "inventory_models.py",
        "sbom_persistence_models.py",
        "inventory_contracts.py",
    ]
    for name in unchanged:
        path = "backend/src/ai_intel/assets/" + name
        assert git("show", f"{BASE}:{path}") == git("show", f"{CODE}:{path}")
    for path in (
        "backend/src/ai_intel/infrastructure/models/json_output.py",
        "backend/pyproject.toml",
        "backend/uv.lock",
    ):
        assert git("show", f"{BASE}:{path}") == git("show", f"{CODE}:{path}")
    for path in (
        "backend/src/ai_intel/assets/inventory.py",
        "backend/src/ai_intel/assets/sbom_inventory_contracts.py",
        "backend/tests/unit/test_r11_sbom_inventory_uri_privacy.py",
        "backend/tests/integration/test_r11_sbom_inventory_uri_privacy.py",
    ):
        assert git("show", f"b4e2697164669ed816661c375cbda7c58b269f3e:{path}") == git(
            "show", f"{CODE}:{path}"
        )
    test_trees = []
    for revision in (BASE, CODE):
        entries = git("ls-tree", "-r", revision, "backend/tests").decode().splitlines()
        test_trees.append(
            dict((entry.split("\t", 1)[1], entry.split("\t", 1)[0]) for entry in entries)
        )
    original_tests, current_tests = test_trees
    for path, blob in original_tests.items():
        assert blob == current_tests[path]
    copies = []
    for relative in ("test_review_probes.py", "resources/test_r11_sbom_inventory_postgres.py"):
        copied = (RUN / relative).read_bytes()
        original = (REVIEW_RUN / relative).read_bytes()
        assert copied == original
        copies.append(
            {
                "copy": relative,
                "source": str(REVIEW_RUN / relative),
                "raw_sha256": sha(copied),
                "bytes_identical": True,
            }
        )
    for target, original in (
        ("test_fix1_probes.py", "test_fix1_probes.py"),
        (
            "fix1_resources/test_r11_sbom_inventory_postgres.py",
            "resources/test_r11_sbom_inventory_postgres.py",
        ),
    ):
        copied = (RUN / target).read_bytes()
        source = FIX1_REVIEW_RUN / original
        assert copied == source.read_bytes()
        copies.append(
            {
                "copy": target,
                "source": str(source),
                "raw_sha256": sha(copied),
                "bytes_identical": True,
            }
        )
    write_json(
        RUN / "frozen_source_proof.json",
        {
            "baseline": BASE,
            "code_commit": CODE,
            "sources": sources,
            "protected_source_and_dependencies_unchanged": True,
            "all_baseline_tests_unchanged_count": len(original_tests),
            "prior_privacy_33_22_inputs_assertions_and_dto_unchanged": True,
            "review_copies": copies,
        },
    )
    xmls = []
    for path in sorted(RUN.glob("*.xml")):
        tree = ElementTree.fromstring(path.read_bytes())
        suites = tree.findall("testsuite")
        xmls.append(
            {
                "path": path.name,
                "tests": sum(int(s.attrib.get("tests", 0)) for s in suites),
                "failures": sum(int(s.attrib.get("failures", 0)) for s in suites),
                "errors": sum(int(s.attrib.get("errors", 0)) for s in suites),
                "skips": sum(int(s.attrib.get("skipped", 0)) for s in suites),
            }
        )
    write_json(RUN / "junit_summary.json", xmls)
    report = REPORT.read_bytes()
    stamp = "\n实际最终装订时间：" + start.isoformat(timespec="seconds") + "。\n"
    REPORT.write_bytes(report + stamp.encode())
    report = REPORT.read_bytes()
    (RUN / "report_raw.md.gz").write_bytes(gzip.compress(report, mtime=0))
    write_json(
        RUN / "report_write_receipt.json",
        {
            "start": start.isoformat(timespec="seconds"),
            "end": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
            "scope": "final_report_write_initial_creation_not_separately_timed",
            "raw_report_sha256": sha(report),
            "git_filtered_report_blob": git(
                "hash-object", "--path", str(REPORT.relative_to(ROOT)), str(REPORT)
            )
            .decode()
            .strip(),
            "code_commit": CODE,
            "material_commit": None,
        },
    )
    excluded = {"artifact_manifest.json", "seal_receipt.json"}
    records = []
    for path in [REPORT, *(path for path in sorted(RUN.rglob("*")) if path.is_file())]:
        if path.name in excluded or "__pycache__" in path.parts:
            continue
        raw = path.read_bytes()
        item = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": len(raw),
            "sha256": sha(raw),
        }
        if path == REPORT:
            item["git_lf_sha256"] = sha(raw.replace(b"\r\n", b"\n"))
            item["exact_raw_copy"] = (
                "reports/runs/recovery_r11_sbom_inventory_privacy_fix1_20261016/report_raw.md.gz"
            )
        elif path.suffix == ".gz":
            item["gzip_raw_sha256"] = sha(gzip.decompress(raw))
        records.append(item)
    write_json(
        RUN / "artifact_manifest.json",
        {"code_commit": CODE, "material_commit": None, "entries": records},
    )
    for item in records:
        assert sha((ROOT / item["path"]).read_bytes()) == item["sha256"]
    receipt = {
        "code_commit": CODE,
        "material_commit": None,
        "files": len(records),
        "manifest_sha256": sha((RUN / "artifact_manifest.json").read_bytes()),
        "finished_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "all_raw_bytes_verified": True,
        "external_calls": 0,
        "fees": 0,
    }
    write_json(RUN / "seal_receipt.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
