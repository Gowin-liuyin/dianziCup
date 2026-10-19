"""Copy the frozen corrected PG test as review evidence while keeping production at Root48."""

import hashlib
import json
import subprocess

import review_checks

ROOT, RUN = review_checks.ROOT, review_checks.RUN
SOURCE = "6bb19fcdbf5c8242142c3f61e338b98a29bc5501"
PRODUCT = "48f96b5ba35d19f5e26868a2bccd5b124afb2bd0"


def main():
    command = ["git", "diff", "--quiet", PRODUCT, "HEAD", "--", "backend/src", "backend/migrations", "contracts", "progress", "frontend", "docs"]
    assert subprocess.run(command, cwd=ROOT).returncode == 0
    assert subprocess.run(["git", "diff", "--quiet", PRODUCT, SOURCE, "--", "backend/src", "backend/migrations", "contracts", "progress", "frontend", "docs"], cwd=ROOT).returncode == 0
    path = "backend/tests/integration/test_r06_revision_mode_read_pg.py"
    original = subprocess.check_output(["git", "show", SOURCE + ":" + path], cwd=ROOT)
    target = RUN / "test_fixed_revision_mode_read_pg.py"
    if target.exists():
        assert target.read_bytes() == original
    else:
        target.write_bytes(original)
    contract = "backend/tests/contract/test_r06_revision_mode_fixture_input_contract.py"
    contract_blob = subprocess.check_output(["git", "show", SOURCE + ":" + contract], cwd=ROOT)
    contract_target = RUN / "test_fixed_revision_mode_fixture_input_contract.py"
    if contract_target.exists():
        assert contract_target.read_bytes() == contract_blob
    else:
        contract_target.write_bytes(contract_blob)
    record = {"prepared_at": review_checks.checks.now(), "actual_product_sha": PRODUCT, "test_source_sha": SOURCE, "test_material_sha": "81840ea42ae1425dfa1468eafed7edb49b440357", "copied_test": str(target), "original_path": path, "test_raw_sha256": hashlib.sha256(original).hexdigest(), "copied_test_is_exact_git_blob": target.read_bytes() == original, "business_files_changed": 0, "original_pg_oracles_changed": 0, "source_bindings_catalog_only": True}
    binding = RUN / "recheck_source_binding.json"
    if binding.exists():
        previous = json.loads(binding.read_bytes())
        assert previous["test_raw_sha256"] == record["test_raw_sha256"]
        assert previous["actual_product_sha"] == record["actual_product_sha"]
    else:
        binding.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
