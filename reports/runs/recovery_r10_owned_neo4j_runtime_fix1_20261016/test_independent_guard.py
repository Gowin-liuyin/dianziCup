"""Exercise frozen ownership rejection with synthetic state and no live stop."""

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import runtime


@pytest.fixture
def owned_case():
    fixture = json.loads(
        (Path(__file__).resolve().parent / "fixture_owned_case.json").read_text()
    )
    assert fixture["fixture_mode"] == "synthetic_owned_identity_only"
    resource, container = fixture["resource"], fixture["container"]
    identity = resource["container_process"]
    with (
        patch.object(runtime, "BOOT_FILE", Mock(read_text=lambda: resource["boot_id"])),
        patch.object(runtime, "process_identity", return_value=identity),
    ):
        yield resource, container


@pytest.mark.parametrize(
    "change",
    [
        "old_cid",
        "fake_creator",
        "wrong_volume_name",
        "wrong_volume_path",
        "wrong_creation",
        "wrong_image",
    ],
)
def test_mismatched_ownership_never_stops(owned_case, change):
    resource, container = copy.deepcopy(owned_case)
    if change == "old_cid":
        container["id"] = resource["prior_container_id"]
    elif change == "fake_creator":
        container["labels"]["dianzi.creator_token"] = "unrelated-creator"
    elif change == "wrong_volume_name":
        container["mounts"][0]["Name"] = "unrelated-volume"
    elif change == "wrong_volume_path":
        container["mounts"][0]["Source"] = "/other-tenant/_data"
    elif change == "wrong_creation":
        container["created"] = "new-created-at"
    elif change == "wrong_image":
        container["image_id"] = "sha256:unrelated-image"
    with (
        patch.object(runtime, "OWNED") as owned,
        patch.object(runtime, "inspect_container", return_value=container),
        patch.object(runtime, "docker") as docker,
    ):
        owned.__truediv__.return_value.read_text.return_value = json.dumps(resource)
        with pytest.raises(AssertionError):
            runtime.stop_owned("synthetic_negative")
        docker.assert_not_called()


def test_reused_pid_never_stops(owned_case):
    resource, container = copy.deepcopy(owned_case)
    observed = copy.deepcopy(resource["container_process"])
    observed["start_ticks"] = str(int(observed["start_ticks"]) + 1)
    with (
        patch.object(runtime, "OWNED") as owned,
        patch.object(runtime, "inspect_container", return_value=container),
        patch.object(runtime, "process_identity", return_value=observed),
        patch.object(runtime, "docker") as docker,
    ):
        owned.__truediv__.return_value.read_text.return_value = json.dumps(resource)
        with pytest.raises(AssertionError):
            runtime.stop_owned("synthetic_reused_pid")
        docker.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("missing identity"),
        PermissionError("unreadable identity"),
        json.JSONDecodeError("invalid identity", "x", 0),
    ],
)
def test_unknown_read_fails_closed(owned_case, failure):
    with (
        patch.object(runtime, "OWNED") as owned,
        patch.object(runtime, "inspect_container") as inspect,
        patch.object(runtime, "docker") as docker,
    ):
        owned.__truediv__.return_value.read_text.side_effect = failure
        with pytest.raises(type(failure)):
            runtime.stop_owned("synthetic_unknown")
        inspect.assert_not_called()
        docker.assert_not_called()


def test_inspection_failure_never_stops(owned_case):
    resource, _ = owned_case
    with (
        patch.object(runtime, "OWNED") as owned,
        patch.object(
            runtime, "inspect_container", side_effect=RuntimeError("unreachable daemon")
        ),
        patch.object(runtime, "docker") as docker,
    ):
        owned.__truediv__.return_value.read_text.return_value = json.dumps(resource)
        with pytest.raises(RuntimeError):
            runtime.stop_owned("synthetic_unknown_daemon")
        docker.assert_not_called()


def test_original_45_second_start_window_and_deadline(owned_case):
    resource, _ = copy.deepcopy(owned_case)
    at = datetime(2026, 10, 16, 10, 0, tzinfo=timezone(timedelta(hours=8)))
    old_heartbeat = {
        "container_id": resource["prior_container_id"],
        "at": "2020-01-01T00:00:00Z",
    }
    with patch.object(runtime, "now", return_value=at):
        assert runtime.heartbeat_failure(resource, old_heartbeat, 45) is None
        assert (
            runtime.heartbeat_failure(resource, old_heartbeat, 45.001)
            == "guardian_current_heartbeat_missing"
        )
        resource["deadline"] = at.isoformat()
        assert runtime.heartbeat_failure(resource, None, 0) == "guardian_deadline"


def test_creator_and_generation_bind_current_heartbeat(owned_case):
    resource, _ = copy.deepcopy(owned_case)
    heartbeat = {
        "runtime_generation": resource["runtime_generation"],
        "container_id": resource["container_id"],
        "supervisor": resource["supervisor"],
        "creator_token": resource["creator_token"],
        "generation": resource["supervisor"]["start_ticks"],
        "at": runtime.now().isoformat(),
    }
    assert runtime.heartbeat_failure(resource, heartbeat, 46) is None
    heartbeat["creator_token"] = "fake-creator"
    assert (
        runtime.heartbeat_failure(resource, heartbeat, 46)
        == "guardian_heartbeat_identity_mismatch"
    )
    heartbeat["creator_token"] = resource["creator_token"]
    heartbeat["generation"] = "reused-supervisor-generation"
    assert (
        runtime.heartbeat_failure(resource, heartbeat, 46)
        == "guardian_heartbeat_identity_mismatch"
    )


@pytest.mark.parametrize("change", ["forged_owner", "wrong_runtime_generation"])
def test_fix_namespace_cannot_adopt_other_resource(owned_case, change):
    resource, container = copy.deepcopy(owned_case)
    if change == "forged_owner":
        container["labels"]["dianzi.owner"] = "unrelated-owner"
    else:
        container["labels"]["dianzi.runtime_generation"] = "old-generation"
    with (
        patch.object(runtime, "OWNED") as owned,
        patch.object(runtime, "inspect_container", return_value=container),
        patch.object(runtime, "docker") as docker,
    ):
        owned.__truediv__.return_value.read_text.return_value = json.dumps(resource)
        with pytest.raises(AssertionError):
            runtime.stop_owned("synthetic_fix_negative")
        docker.assert_not_called()


def test_old_supervisor_heartbeat_is_rejected(owned_case):
    resource, _ = owned_case
    heartbeat = {
        "container_id": resource["container_id"],
        "supervisor": {"pid": 1, "start_ticks": "old"},
        "at": runtime.now().isoformat(),
    }
    assert (
        runtime.heartbeat_failure(resource, heartbeat, 1)
        == "guardian_heartbeat_supervisor_mismatch"
    )


def test_old_runtime_heartbeat_is_rejected(owned_case):
    resource, _ = owned_case
    heartbeat = {
        "container_id": resource["container_id"],
        "supervisor": resource["supervisor"],
        "creator_token": resource["creator_token"],
        "generation": resource["supervisor"]["start_ticks"],
        "runtime_generation": "old-runtime",
        "at": runtime.now().isoformat(),
    }
    assert (
        runtime.heartbeat_failure(resource, heartbeat, 1)
        == "guardian_heartbeat_runtime_generation_mismatch"
    )
