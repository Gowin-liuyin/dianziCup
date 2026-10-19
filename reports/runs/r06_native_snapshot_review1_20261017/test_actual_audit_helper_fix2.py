"""Public source-map fixtures validate new constants without actual kernel audit or secrets."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
OLD = ROOT / "reports/runs/recovery_r06_bootstrap_recovery_fix1_20261017/audit_failed_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("new_actual_audit_fixture", ROOT / "reports/runs/r06_actual_audit_helper_20261017/audit_failed_bootstrap.py")
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
EXPECTED_PINS = {
    "core_source_sha": "37ffe6da1d9a258359363d42488d236b7c00ad87",
    "operations_source_sha": "81053fd680dbfb275bfcc511ae44f573340efd56",
}
BOUND = ROOT / "reports/runs/r06_native_process_snapshot_bound_fix2_20261017/handoff"


def test_only_three_package_constants_differ_and_all_function_ast_is_original():
    old = ast.parse(OLD.read_bytes())
    current = ast.parse((ROOT / "reports/runs/r06_actual_audit_helper_20261017/audit_failed_bootstrap.py").read_bytes())
    allowed = {"PACKAGE_MANIFEST", "PACKAGE_MANIFEST_SHA256", "PACKAGE_SOURCE_PINS"}
    def retained(tree):
        return [node for node in tree.body if not (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in allowed for target in node.targets))]
    assert ast.dump(ast.Module(body=retained(current), type_ignores=[])) == ast.dump(ast.Module(body=retained(old), type_ignores=[]))
    old_functions = [ast.dump(node) for node in ast.walk(old) if isinstance(node, ast.FunctionDef)]
    current_functions = [ast.dump(node) for node in ast.walk(current) if isinstance(node, ast.FunctionDef)]
    assert old_functions == current_functions
    assert AUDIT.REPOSITORY == ROOT
    assert AUDIT.PACKAGE_MANIFEST == BOUND / "source_manifest.json"
    assert AUDIT.PACKAGE_MANIFEST_SHA256 == "6a1f1cccb510dffe00fa379166d2f423731baf67fa124853493d3b347f80ba55"
    assert AUDIT.PACKAGE_SOURCE_PINS == EXPECTED_PINS


def test_real_new_manifest_and_twenty_source_binding_are_valid_fixture_input(tmp_path, monkeypatch):
    assert 65536 < AUDIT.PACKAGE_MANIFEST.stat().st_size <= 262144
    assert AUDIT.package_source_pins() == EXPECTED_PINS
    binding = json.loads((BOUND / "runtime_binding.pending.json").read_bytes())
    manifest = json.loads(AUDIT.PACKAGE_MANIFEST.read_bytes())
    core, ops = tmp_path / "fixture_core", tmp_path / "fixture_ops"
    core.mkdir()
    ops.mkdir()
    source_count = 0
    for row in manifest["source_23"]:
        if row["component"] == "observer":
            continue
        source = ROOT / row["candidate_path"]
        target = core if row["component"] == "core" else ops
        (target / source.name).write_bytes(source.read_bytes())
        source_count += 1
    assert source_count == 20
    monkeypatch.setattr(AUDIT, "CORE", core)
    monkeypatch.setattr(AUDIT, "OPS", ops)
    AUDIT.verify_installed_sources(binding)
    assert set(AUDIT.verify_frozen_job(binding)) == {"runtime_limits.py", "guardian.py"}
    with pytest.raises(AUDIT.AuditError, match="metadata_size_exceeded"):
        AUDIT.read_object(AUDIT.PACKAGE_MANIFEST)


@pytest.mark.parametrize("field", ["core_source_sha", "operations_source_sha"])
def test_wrong_new_source_pin_refuses_before_frozen_source_read(field, monkeypatch):
    binding = json.loads((BOUND / "runtime_binding.pending.json").read_bytes())
    binding[field] = "0" * 40
    def no_git_read(*_arguments):
        raise AssertionError("wrong pin must refuse before frozen source read")
    monkeypatch.setattr(AUDIT, "frozen_source", no_git_read)
    with pytest.raises(AUDIT.AuditError):
        AUDIT.verify_frozen_job(binding)


def test_missing_manifest_is_not_an_empty_success(tmp_path, monkeypatch):
    monkeypatch.setattr(AUDIT, "PACKAGE_MANIFEST", tmp_path / "absent_manifest.json")
    with pytest.raises(AUDIT.AuditError, match="required_file_absent"):
        AUDIT.package_source_pins()


@pytest.mark.parametrize("failure", ["digest", "pins"])
def test_new_manifest_tampering_refuses(tmp_path, monkeypatch, failure):
    raw = AUDIT.PACKAGE_MANIFEST.read_bytes()
    if failure == "digest":
        raw += b" "
    else:
        manifest = json.loads(raw)
        manifest["operations_source_sha"] = "0" * 40
        raw = json.dumps(manifest).encode()
        monkeypatch.setattr(AUDIT, "PACKAGE_MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    path = tmp_path / "tampered_manifest.json"
    path.write_bytes(raw)
    monkeypatch.setattr(AUDIT, "PACKAGE_MANIFEST", path)
    with pytest.raises(AUDIT.AuditError):
        AUDIT.package_source_pins()
