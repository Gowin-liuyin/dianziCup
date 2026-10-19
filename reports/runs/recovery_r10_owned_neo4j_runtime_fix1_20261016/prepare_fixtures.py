"""Reuse the original guard cases with an explicit synthetic fix-generation fixture."""

import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
original = OUTPUT.parent / "recovery_r10_owned_neo4j_runtime_20261016"
resource = json.loads((original / "resource_started.json").read_text())
container = json.loads((original / "snapshot.json").read_text())["container"]
resource["container_id"] = "e" * 64
resource["prior_container_id"] = (
    "c0d49f69954c9d7b5d3ab0420347b99d96e9fdbeaf87ece3032b8c3430cd41ab"
)
resource["runtime_generation"] = "r10-owned-runtime-fix1-20261016"
container["id"] = resource["container_id"]
container["labels"]["dianzi.runtime_generation"] = resource["runtime_generation"]
(OUTPUT / "fixture_owned_case.json").write_text(
    json.dumps(
        {
            "fixture_mode": "synthetic_owned_identity_only",
            "resource": resource,
            "container": container,
        },
        indent=2,
    )
    + "\n"
)
source_path = Path(
    "D:/wt/r10-owned-runtime-review1/reports/runs/recovery_r10_owned_runtime_review1_20261016/test_independent_guard.py"
)
source = source_path.read_text()
start = source.index("FROZEN =")
end = source.index("@pytest.mark.parametrize")
replacement = """import runtime


@pytest.fixture
def owned_case():
    fixture = json.loads((Path(__file__).resolve().parent / "fixture_owned_case.json").read_text())
    assert fixture["fixture_mode"] == "synthetic_owned_identity_only"
    resource, container = fixture["resource"], fixture["container"]
    identity = resource["container_process"]
    with patch.object(runtime, "BOOT_FILE", Mock(read_text=lambda: resource["boot_id"])), patch.object(runtime, "process_identity", return_value=identity):
        yield resource, container


"""
source = source[:start] + replacement + source[end:]
source = source.replace("import importlib.util\n", "")
source = source.replace(
    'heartbeat = {\n        "container_id": resource["container_id"],',
    'heartbeat = {\n        "runtime_generation": resource["runtime_generation"],\n        "container_id": resource["container_id"],',
)
source += """

@pytest.mark.parametrize("change", ["forged_owner", "wrong_runtime_generation"])
def test_fix_namespace_cannot_adopt_other_resource(owned_case, change):
    resource, container = copy.deepcopy(owned_case)
    if change == "forged_owner":
        container["labels"]["dianzi.owner"] = "unrelated-owner"
    else:
        container["labels"]["dianzi.runtime_generation"] = "old-generation"
    with patch.object(runtime, "OWNED") as owned, patch.object(runtime, "inspect_container", return_value=container), patch.object(runtime, "docker") as docker:
        owned.__truediv__.return_value.read_text.return_value = json.dumps(resource)
        with pytest.raises(AssertionError):
            runtime.stop_owned("synthetic_fix_negative")
        docker.assert_not_called()


def test_old_supervisor_heartbeat_is_rejected(owned_case):
    resource, _ = owned_case
    heartbeat = {"container_id": resource["container_id"], "supervisor": {"pid": 1, "start_ticks": "old"}, "at": runtime.now().isoformat()}
    assert runtime.heartbeat_failure(resource, heartbeat, 1) == "guardian_heartbeat_supervisor_mismatch"


def test_old_runtime_heartbeat_is_rejected(owned_case):
    resource, _ = owned_case
    heartbeat = {"container_id": resource["container_id"], "supervisor": resource["supervisor"], "creator_token": resource["creator_token"], "generation": resource["supervisor"]["start_ticks"], "runtime_generation": "old-runtime", "at": runtime.now().isoformat()}
    assert runtime.heartbeat_failure(resource, heartbeat, 1) == "guardian_heartbeat_runtime_generation_mismatch"
"""
(OUTPUT / "test_independent_guard.py").write_text(source)
print(
    json.dumps(
        {
            "fixture_mode": "synthetic_owned_identity_only",
            "original_independent_cases": 13,
            "new_generation_cases": 4,
            "real_resource_mutations": 0,
        }
    )
)
