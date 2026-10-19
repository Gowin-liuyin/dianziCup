"""Independent public fixtures preserve duplicate, size, and package-shape refusals."""

import hashlib
import json

import pytest
from test_actual_audit_helper_fix2 import AUDIT


@pytest.mark.parametrize("fault,label", [
    ("duplicate", "duplicate_json_key"),
    ("oversize", "package_manifest_size_exceeded"),
    ("shape", "package_manifest_shape_differs"),
])
def test_new_package_manifest_refuses_exact_boundary_fault(tmp_path, monkeypatch, fault, label):
    raw = AUDIT.PACKAGE_MANIFEST.read_bytes()
    if fault == "duplicate":
        raw = b'{"core_source_sha":"duplicate",' + raw[1:]
    elif fault == "oversize":
        raw += b" " * (262145 - len(raw))
    else:
        value = json.loads(raw)
        value["source_23"] = []
        raw = json.dumps(value).encode()
    path = tmp_path / "fixture_manifest.json"
    path.write_bytes(raw)
    monkeypatch.setattr(AUDIT, "PACKAGE_MANIFEST", path)
    monkeypatch.setattr(AUDIT, "PACKAGE_MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(AUDIT.AuditError, match=label):
        AUDIT.package_source_pins()
