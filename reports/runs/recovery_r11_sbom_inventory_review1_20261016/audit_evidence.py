"""对冻结来源、原始材料和独立结果做字节核对；不接触业务状态。"""

import gzip
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry
from referencing.exceptions import NoSuchResource
from review_runner import AUTHOR_RUN, ROOT, RUN, now

CODE = "0892b6af7fbc0c16651aeb25f14493fb4c3fa48d"
MATERIAL = "c0369e6b7cb71c19f7594da8737e6bb3717893f3"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    start = now()
    assert git("rev-parse", "HEAD").decode().strip() == MATERIAL
    manifest_raw = (AUTHOR_RUN / "artifact_manifest.json").read_bytes()
    assert sha(manifest_raw) == "7aa107ebf586796c3d7aad2574d5617de60665af8dbee47a69d2cd451aa27f82"
    manifest = json.loads(manifest_raw)
    source = json.loads((AUTHOR_RUN / "frozen_source_proof.json").read_text())
    evidence = []
    for item in manifest["entries"]:
        path = ROOT / item["path"]
        raw = path.read_bytes()
        if item.get("exact_raw_copy"):
            raw = gzip.decompress((ROOT / item["exact_raw_copy"]).read_bytes())
            assert raw.replace(b"\r\n", b"\n") == path.read_bytes().replace(b"\r\n", b"\n")
        assert sha(raw) == item["sha256"], item["path"]
        evidence.append({"path": item["path"], "bytes": len(raw), "verified_raw_sha256": sha(raw)})
    blobs = RUN / "source_blobs"
    blobs.mkdir(exist_ok=True)
    checked_sources = []
    for index, item in enumerate(source["sources"]):
        frozen = git("show", CODE + ":" + item["path"])
        filtered = git("hash-object", "--path=" + item["path"], item["path"]).decode().strip()
        assert filtered == item["git_blob"]
        assert sha(frozen) == item["git_lf_sha256"]
        stored = blobs / (f"{index:02d}_" + Path(item["path"]).name + ".gz")
        stored.write_bytes(gzip.compress(frozen, mtime=0))
        checked_sources.append(
            {
                "path": item["path"],
                "frozen_git_blob": item["git_blob"],
                "sha256": sha(frozen),
                "working_tree_filtered_matches": True,
                "source_blob_copy": stored.relative_to(ROOT).as_posix(),
            }
        )
    summary = {}
    for label in ("pure", "pg_sbom", "pg_legacy", "pg_probes", "pg_probes_second"):
        tree = ET.parse(RUN / (label + ".xml"))
        cases = list(tree.getroot().iter("testcase"))
        counts = {
            "tests": len(cases),
            "failures": sum(case.find("failure") is not None for case in cases),
            "errors": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases),
        }
        counts["passed"] = (
            counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
        )
        counts["classifications"] = {
            group: sum(group in case.attrib.get("classname", "") for case in cases)
            for group in ("unit", "contract", "security")
        }
        summary[label] = counts
    sys.path.insert(0, str(RUN / "resources"))
    import test_r11_sbom_inventory_postgres as fixture

    schema_raw = gzip.decompress(
        (
            ROOT / "reports/runs/recovery_r11_sbom_adapters_20261016/spdx-2.3.1.schema.json.gz"
        ).read_bytes()
    )

    def prohibit_reference(uri):
        raise NoSuchResource(ref=uri)

    validator = Draft7Validator(
        json.loads(schema_raw),
        registry=Registry(retrieve=prohibit_reference),
        format_checker=FormatChecker(),
    )
    uri_checks = []
    for uri in (
        "postgresql://synthetic_user:synthetic_password@db.internal:5432/private",
        "file:///C:/private/synthetic-parent",
        "https://synthetic_user:synthetic_password@example.test/sbom",
    ):
        value = fixture.spdx_document()
        value["externalDocumentRefs"][0]["spdxDocument"] = uri
        errors = list(validator.iter_errors(value))
        uri_checks.append(
            {
                "synthetic_uri": uri,
                "schema_errors": len(errors),
                "paths": [list(error.absolute_path) for error in errors],
            }
        )
    frontend = "frontend/src/features/assets/asset-contracts.ts"
    frontend_raw = git("show", "1acf4911731f654e11b6173b24db21214d753c02:" + frontend)
    assert "source_kind: string" in frontend_raw.decode()
    (RUN / "frontend_contract_frozen.ts.gz").write_bytes(gzip.compress(frontend_raw, mtime=0))
    receipt = {
        "start": start,
        "end": now(),
        "code_commit": CODE,
        "material_commit": MATERIAL,
        "author_manifest_sha256": sha(manifest_raw),
        "author_manifest_entries": len(evidence),
        "author_report_raw_sha256": sha(
            gzip.decompress((AUTHOR_RUN / "report_raw.md.gz").read_bytes())
        ),
        "author_materials": evidence,
        "source_blobs": checked_sources,
        "junit": summary,
        "protected_uri_official_schema_checks": uri_checks,
        "official_spdx_schema_sha256": sha(schema_raw),
        "frontend_read_only": {
            "commit": "1acf4911731f654e11b6173b24db21214d753c02",
            "path": frontend,
            "sha256": sha(frontend_raw),
            "runtime": "not_run",
        },
        "git_status": git("status", "--short").decode(),
    }
    (RUN / "audit_receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in (
                    "code_commit",
                    "material_commit",
                    "author_manifest_entries",
                    "author_manifest_sha256",
                    "author_report_raw_sha256",
                    "junit",
                    "protected_uri_official_schema_checks",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
