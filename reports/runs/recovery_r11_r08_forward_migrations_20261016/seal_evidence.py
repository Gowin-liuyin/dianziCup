"""Bind raw evidence, frozen implementation and reviewed upstream materials by hash."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from run_checks import ROOT, RUN, execute, now

CODE_SHA = "c842333fe56a4ab3018a3216a8ddcd6a34639ae1"
MATERIAL_ASSETS = "bc8798cf5efc81e210a429884930ca545af43ad8"
MATERIAL_AGGREGATES = "a76374ca9200945441a83421050eceef00db47d8"


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def main():
    execute(
        "frozen_callers_rg",
        [
            "rg",
            "-n",
            "InventoryService|AggregateService|PostgresAggregateRepository|"
            "metadata|^revision|^down_revision",
            "backend/src/ai_intel/assets",
            "backend/src/ai_intel/infrastructure/database.py",
            "backend/migrations/versions",
        ],
        cwd=ROOT,
    )
    assert (
        git(
            "diff",
            CODE_SHA,
            "--",
            "backend/src",
            "backend/tests",
            "backend/migrations",
            "backend/pyproject.toml",
            "backend/uv.lock",
            "progress",
        )
        == b""
    )
    source_paths = [
        "backend/migrations/versions/0018_asset_inventory.py",
        "backend/migrations/versions/0019_aggregate_observations.py",
        "backend/tests/contract/test_r11_r08_forward_migrations.py",
        "backend/tests/integration/test_r11_r08_forward_migration_schema.py",
        "backend/tests/integration/test_r11_r08_migration_head_regression.py",
        "backend/tests/security/test_r11_r08_forward_migration_boundaries.py",
    ]
    sources = []
    for path in source_paths:
        blob = git("show", CODE_SHA + ":" + path)
        sources.append(
            {
                "path": path,
                "git_blob_sha256": digest(blob),
                "raw_sha256": digest((ROOT / path).read_bytes()),
            }
        )
    upstream = []
    for material, paths in (
        (
            MATERIAL_ASSETS,
            [
                "inventory_models.py",
                "inventory.py",
                "inventory_contracts.py",
                "inventory_routes.py",
                "manifest_parser.py",
            ],
        ),
        (
            MATERIAL_AGGREGATES,
            ["aggregate_persistence_models.py", "aggregate_repository.py", "aggregate_service.py"],
        ),
    ):
        for file_name in paths:
            path = "backend/src/ai_intel/assets/" + file_name
            original = git("show", material + ":" + path)
            frozen = git("show", CODE_SHA + ":" + path)
            assert original == frozen
            upstream.append(
                {
                    "path": path,
                    "material_commit": material,
                    "material_tree": git("rev-parse", material + "^{tree}").decode().strip(),
                    "git_blob_sha256": digest(frozen),
                    "matches": True,
                }
            )
    reviews = []
    for path in (
        Path(
            "D:/wt/r11-inventory-review1/reports/reviews/recovery/"
            "G-D-R11-asset-inventory-review-1.md"
        ),
        Path(
            "D:/wt/r08-persistence-recheck1/reports/reviews/recovery/"
            "G-C-R08-aggregate-persistence-review-1-recheck.md"
        ),
    ):
        reviews.append({"path": str(path), "raw_sha256": digest(path.read_bytes())})
    (RUN / "source_manifest.json").write_text(
        json.dumps(
            {
                "sealed_at": now(),
                "code_sha": CODE_SHA,
                "code_tree": git("rev-parse", CODE_SHA + "^{tree}").decode().strip(),
                "sources": sources,
                "upstream_sources": upstream,
                "independent_reviews": reviews,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    counts = {}
    for name in (
        "contract_red",
        "contract_green",
        "pure_regression",
        "frozen_pure",
        "pg_original_head",
        "pg_reflection",
        "pg_new_security",
        "pg_frozen_regression",
    ):
        suites = ET.parse(RUN / f"{name}.xml").getroot().iter("testsuite")
        summary = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
        for suite in suites:
            for key in summary:
                summary[key] += int(suite.attrib.get(key, 0))
        counts[name] = summary
    assert counts["frozen_pure"] == {"tests": 78, "failures": 0, "errors": 0, "skipped": 0}
    assert counts["pg_frozen_regression"] == {
        "tests": 100,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }
    (RUN / "test_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")
    raw_entries = []
    for path in sorted(RUN.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.name != "artifact_manifest.json"
        ):
            content = path.read_bytes()
            raw_entries.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "length": len(content),
                    "raw_sha256": digest(content),
                }
            )
    report = ROOT / "reports/tasks/R11-R08-forward-migrations.md"
    if report.exists():
        content = report.read_bytes()
        raw_entries.append(
            {
                "path": report.relative_to(ROOT).as_posix(),
                "length": len(content),
                "raw_sha256": digest(content),
            }
        )
    manifest = {
        "sealed_at": now(),
        "code_sha": CODE_SHA,
        "upstream_material_shas": [MATERIAL_ASSETS, MATERIAL_AGGREGATES],
        "basis": "raw bytes; source manifest separately records Git blob bytes",
        "files": raw_entries,
    }
    manifest_path = RUN / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for item in raw_entries:
        content = (ROOT / item["path"]).read_bytes()
        assert len(content) == item["length"] and digest(content) == item["raw_sha256"]
    print(
        json.dumps(
            {
                "raw_entries": len(raw_entries),
                "upstream_exact_sources": len(upstream),
                "unique_successful_cases": 178,
                "manifest_raw_sha256": digest(manifest_path.read_bytes()),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
