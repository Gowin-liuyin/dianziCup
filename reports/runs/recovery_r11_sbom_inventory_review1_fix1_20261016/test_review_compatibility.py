"""版本容量与侧车隐私的独立合同/真实HTTP探针。"""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry
from referencing.exceptions import NoSuchResource
from sqlalchemy import select

from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.domain.access import Role

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
spec = importlib.util.spec_from_file_location(
    "compatibility_resource", RUN / "resources/test_r11_sbom_inventory_postgres.py"
)
resource = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resource)
sbom_engine = resource.sbom_engine
sbom_api = resource.sbom_api


def validate(value, schema_name):
    raw = gzip.decompress(
        (
            ROOT
            / "reports/runs/recovery_r11_sbom_adapters_20261016"
            / (schema_name + ".schema.json.gz")
        ).read_bytes()
    )

    def prohibit_reference(uri):
        raise NoSuchResource(ref=uri)

    Draft7Validator(
        json.loads(raw),
        registry=Registry(retrieve=prohibit_reference),
        format_checker=FormatChecker(),
    ).validate(value)


@pytest.mark.parametrize("version", ["1.5", "1.6"])
def test_other_supported_cdx_versions_have_full_10000_real_http_capacity(
    sbom_engine, sbom_api, version
):
    login, _ = sbom_api
    client, headers, _ = login()
    value = {
        "bomFormat": "CycloneDX",
        "specVersion": version,
        "version": 1,
        "components": [
            {"type": "library", "name": f"p{i}", "version": "1", "purl": f"pkg:pypi/p{i}@1"}
            for i in range(10000)
        ],
    }
    validate(value, "cyclonedx-" + version)
    raw = resource.raw_document(value)
    if version == "1.5":
        raw += b" " * (1048576 - len(raw))
    assert len(raw) <= 1048576
    created = resource.upload(client, headers, raw)
    assert created.status_code == 201
    identity = created.json()["asset_id"]
    snapshot = created.json()["snapshot"]
    assert len(snapshot["components"]) == 10000
    assert snapshot["components"][-1]["package_name"] == "p9999"
    assert {item["version"] for item in snapshot["components"]} == {"1"}
    sidecar = client.get(f"/api/assets/{identity}/snapshots/{snapshot['snapshot_id']}/sbom")
    assert sidecar.status_code == 200
    assert sidecar.json()["spec_version"] == version
    assert len(sidecar.json()["component_sources"]) == 10000
    assert sidecar.json()["component_sources"][-1]["source_field_locator"] == "/components/9999"
    with sbom_engine.connect() as connection:
        saved = connection.execute(
            select(asset_snapshots.c.raw_input, asset_snapshots.c.raw_input_sha256).where(
                asset_snapshots.c.snapshot_id == snapshot["snapshot_id"]
            )
        ).one()
    assert bytes(saved[0]) == raw
    assert saved[1] == hashlib.sha256(raw).hexdigest()


def test_protected_source_ref_also_stays_private_for_analyst(sbom_engine, sbom_api):
    login, _ = sbom_api
    client, headers, account = login()
    value = resource.document()
    private_ref = "postgresql://synthetic_user:synthetic_password@db.internal/private"
    value.pop("opaque")
    value["components"][0]["bom-ref"] = private_ref
    value["dependencies"][0]["ref"] = private_ref
    value["compositions"][0]["assemblies"] = [private_ref]
    validate(value, "cyclonedx-1.7")
    created = resource.upload(client, headers, resource.raw_document(value))
    if created.status_code in {400, 422}:
        return
    assert created.status_code == 201
    analyst, _, _ = login(Role.ANALYST, account.tenant_id)
    sidecar = analyst.get(
        f"/api/assets/{created.json()['asset_id']}/snapshots/{created.json()['snapshot']['snapshot_id']}/sbom"
    )
    assert sidecar.status_code == 200
    assert private_ref not in sidecar.text
