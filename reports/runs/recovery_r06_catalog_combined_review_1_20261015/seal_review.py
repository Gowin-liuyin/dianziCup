"""Seal independent evidence and check actual connection values never entered artifacts."""

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-C-R06-catalog-combined-review-1.md"
TARGET = "84301979920bbae7ff0074ebc5a0633f9b31747a"
EXPECTED_FILES = [
    "backend/src/ai_intel/ingestion/source_catalog.py",
    "backend/src/ai_intel/ingestion/catalog_documents.py",
    "backend/src/ai_intel/ingestion/source_documents.py",
    "backend/src/ai_intel/knowledge/revisions.py",
    "backend/src/ai_intel/knowledge/models.py",
    "backend/src/ai_intel/api/document_contracts.py",
    "backend/migrations/versions/0015_catalog_document_metadata.py",
    "backend/tests/integration/test_r05_vector_persistence.py",
    "backend/tests/integration/test_r05_question_api_pg.py",
    "backend/tests/integration/test_r06_catalog_documents_pg.py",
    "fixtures/recorded/r05_legacy_0013_vllm_public_v1.json",
]


def sha(content):
    return hashlib.sha256(content).hexdigest()


def main():
    started = datetime.now(timezone(timedelta(hours=8))).isoformat()
    target = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert target == TARGET
    code_files = {}
    for path in EXPECTED_FILES:
        physical = (ROOT / path).read_bytes()
        frozen = subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=ROOT)
        assert physical.replace(b"\r\n", b"\n") == frozen
        code_files[path] = {"physical_sha256": sha(physical), "git_lf_sha256": sha(frozen)}
    command_records = [json.loads(line) for line in (RUN / "commands.jsonl").read_text().splitlines()]
    assert all(record["public_counts_and_versions_unchanged"] for record in command_records)
    pure = [record for record in command_records if record["mode"] == "pure"]
    assert all(not record["pg_environment_granted"] and "not real_pg" in record["argv"] for record in pure)
    summary = {}
    for name in ["pure_regression", "pure_regression_clean", "original_35", "catalog_21", "catalog_21_recheck", "probes_independent", "probes_compatibility", "probes_registration_recheck"]:
        xml = ElementTree.parse(RUN / f"{name}.xml").getroot()
        suites = list(xml) if xml.tag == "testsuites" else [xml]
        summary[name] = {field: sum(int(suite.attrib.get(field, 0)) for suite in suites) for field in ["tests", "failures", "errors", "skipped"]}
        if name == "pure_regression_clean":
            categories = {}
            for case in xml.iter("testcase"):
                classname = case.attrib["classname"]
                category = next((value for value in ["unit", "contract", "security"] if f".{value}." in classname), "unknown")
                categories[category] = categories.get(category, 0) + 1
            summary[name]["categories"] = categories
    artifacts = {path.name: sha(path.read_bytes()) for path in RUN.iterdir() if path.is_file() and path.name != "seal_manifest.json"}
    connection_info = json.loads(subprocess.check_output(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"], text=True))
    connection_url = connection_info["TEST_DATABASE_URL"]
    forbidden = [connection_url.encode(), unquote(urlsplit(connection_url).password or "").encode()]
    forbidden = [value for value in forbidden if value]
    for path in RUN.iterdir():
        if path.is_file():
            assert not any(value in path.read_bytes() for value in forbidden), "connection leaked in own artifact"
    assert not any(value in REPORT.read_bytes() for value in forbidden), "connection leaked in report"
    archive = json.loads((RUN / "synthetic_temp_archive_manifest.json").read_text())
    assert sha(Path(archive["archive"]).read_bytes()) == archive["sha256"]
    with ZipFile(archive["archive"]) as handle:
        assert all(not any(value in handle.read(name) for value in forbidden) for name in handle.namelist())
    result = {"target_sha": target, "target_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip(), "sealed_at": started, "report": str(REPORT), "report_sha256": sha(REPORT.read_bytes()), "code_files": code_files, "artifacts_sha256": artifacts, "test_counts": summary, "all_pg_public_counts_versions_unchanged": True, "pure_pg_environment_never_granted": True, "exact_connection_values_absent": True, "external_archive_sha256": archive["sha256"], "command_record_count_before_seal": len(command_records)}
    (RUN / "seal_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key:value for key,value in result.items() if key not in {"code_files", "artifacts_sha256"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
