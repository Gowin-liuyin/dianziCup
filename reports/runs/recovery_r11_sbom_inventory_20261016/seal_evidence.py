"""冻结本切片source/Git-LF/公开schema复用与原run字节；不读取账号秘密或改进度。"""

import gzip
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASELINE = "5f32b90b1a34f2d4b6c7f11da10c32b470b55569"
CODE = "0892b6af7fbc0c16651aeb25f14493fb4c3fa48d"


def git(*arguments: str) -> bytes:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = datetime.now(ZoneInfo("Asia/Shanghai"))
    changed = git("diff-tree", "--no-commit-id", "--name-only", "-r", CODE).decode().splitlines()
    paths = [
        *changed,
        "backend/src/ai_intel/assets/sbom_parser.py",
        "backend/src/ai_intel/assets/sbom_persistence_models.py",
        "backend/src/ai_intel/assets/inventory_models.py",
        "backend/src/ai_intel/infrastructure/models/json_output.py",
    ]
    sources = []
    for path in paths:
        raw = (ROOT / path).read_bytes()
        blob = git("show", f"{CODE}:{path}")
        expected = git("rev-parse", f"{CODE}:{path}").decode().strip()
        filtered = git("hash-object", "--path", path, path).decode().strip()
        assert filtered == expected
        assert raw.replace(b"\r\n", b"\n") == blob
        sources.append(
            {
                "path": path,
                "raw_sha256": sha(raw),
                "raw_bytes": len(raw),
                "git_lf_sha256": sha(blob),
                "git_blob": expected,
                "filtered_git_blob_matches": True,
            }
        )
    for path in (
        "backend/src/ai_intel/assets/inventory_models.py",
        "backend/src/ai_intel/infrastructure/models/json_output.py",
    ):
        assert git("show", f"{BASELINE}:{path}") == git("show", f"{CODE}:{path}")
    assert git(
        "show",
        "f6acedcd2b004671c317f55dd058f46e5e517de9:backend/src/ai_intel/assets/sbom_parser.py",
    ) == git("show", f"{CODE}:backend/src/ai_intel/assets/sbom_parser.py")
    write_json(
        RUN / "frozen_source_proof.json",
        {
            "baseline": BASELINE,
            "code_commit": CODE,
            "upstream_adapter_material_commit": "f6acedcd2b004671c317f55dd058f46e5e517de9",
            "root_model_commit": "0532c4f58611e068fc7d5b03da984bc57dbad9f2",
            "local_model_cherry_commit": "e1cad47f",
            "sources": sources,
            "shared_model_json_and_inventory_models_unchanged": True,
            "reviewed_sbom_parser_unchanged": True,
        },
    )
    original = ROOT / "reports/runs/recovery_r11_sbom_adapters_20261016"
    public_material = []
    for name in (
        "cyclonedx-1.5.schema.json",
        "cyclonedx-1.6.schema.json",
        "cyclonedx-1.7.schema.json",
        "spdx-2.3.1.schema.json",
        "synthetic-dense-10000.json",
    ):
        path = original / (name + ".gz")
        compressed = path.read_bytes()
        raw = gzip.decompress(compressed)
        public_material.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "compressed_sha256": sha(compressed),
                "raw_sha256": sha(raw),
                "raw_bytes": len(raw),
                "action": "reused_frozen_public_material_no_network",
            }
        )
    dense = gzip.decompress((original / "synthetic-dense-10000.json.gz").read_bytes())
    assert len(dense) == 797858
    assert sha(dense) == "5a524d5fdc2e9bebef8fafbaa1870080ffb7be896b561da3c11d35a611ffed4d"
    write_json(RUN / "public_material_reuse.json", public_material)
    xmls = []
    for path in sorted(RUN.glob("*.xml")):
        tree = ElementTree.fromstring(path.read_bytes())
        suites = tree.findall("testsuite")
        groups = Counter()
        for case in tree.iter("testcase"):
            groups[case.attrib.get("classname", "")] += 1
        xmls.append(
            {
                "path": path.name,
                "tests": sum(int(s.attrib.get("tests", 0)) for s in suites),
                "failures": sum(int(s.attrib.get("failures", 0)) for s in suites),
                "errors": sum(int(s.attrib.get("errors", 0)) for s in suites),
                "skips": sum(int(s.attrib.get("skipped", 0)) for s in suites),
                "pytest_time_seconds": sum(float(s.attrib.get("time", 0)) for s in suites),
                "groups": dict(groups),
            }
        )
    write_json(RUN / "junit_summary.json", xmls)
    write_json(
        RUN / "runtime_versions.json",
        {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "packages": {
                name: importlib.metadata.version(name)
                for name in (
                    "packageurl-python",
                    "sqlalchemy",
                    "psycopg",
                    "fastapi",
                    "pydantic",
                    "jsonschema",
                    "pytest",
                    "ruff",
                    "mypy",
                )
            },
            "external_model_or_fofa_calls": 0,
            "paid_api_calls": 0,
        },
    )
    frontend = Path("D:/wt/r17-assets-workbench/frontend/src/features/assets/asset-contracts.ts")
    write_json(
        RUN / "frontend_read_only_contract.json",
        {
            "path": str(frontend),
            "source_sha256": sha(frontend.read_bytes()),
            "code_commit": "1acf4911731f654e11b6173b24db21214d753c02",
            "observed_head": "6db161e59e1c081d249b510ac441c93ad2fd295b",
            "verified_git_blob": "f0d3ef11adad3adb0e6f75c60d3725494a364ee4",
            "source_kind_contract": "string",
            "components_maximum": 10000,
            "upload_formats": ["json_manifest_v1", "csv_components_v1"],
            "inspection_only": True,
            "frontend_runtime": "not_run",
            "browser_e2e": "not_run",
        },
    )
    write_json(
        RUN / "seal_preparation_receipt.json",
        {
            "start": started.isoformat(timespec="seconds"),
            "end": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
            "code_commit": CODE,
            "artifact_manifest": "written_after_report_and_quality_checks",
        },
    )
    print(
        json.dumps(
            {
                "source_files": len(sources),
                "public_materials": len(public_material),
                "xml_runs": len(xmls),
                "code_commit": CODE,
            }
        )
    )


if __name__ == "__main__":
    main()
