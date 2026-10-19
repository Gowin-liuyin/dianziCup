"""Check ownership rejection without stopping or creating any real resource."""

import copy
import unittest
from unittest.mock import Mock, patch

import runtime


class OwnedIdentityTests(unittest.TestCase):
    def setUp(self):
        self.resource = {
            "runtime_generation": runtime.RUNTIME_GENERATION,
            "boot_id": "this-boot",
            "container_id": "c" * 64,
            "container_created_at": "created-at",
            "creator_token": "owned-token",
            "deadline": "2026-10-16T19:00:00+08:00",
            "volume_mountpoint": "/owned-volume/_data",
        }
        self.container = {
            "id": "c" * 64,
            "name": "/" + runtime.NAME,
            "image_id": runtime.IMAGE_ID,
            "configured_image": runtime.IMAGE,
            "created": "created-at",
            "labels": {
                "dianzi.runtime_generation": runtime.RUNTIME_GENERATION,
                "dianzi.owner": runtime.OWNER,
                "dianzi.resource_id": runtime.NAME,
                "dianzi.creator_token": "owned-token",
                "dianzi.deadline": self.resource["deadline"],
            },
            "mounts": [
                {
                    "Destination": "/data",
                    "Type": "volume",
                    "Name": runtime.VOLUME,
                    "Source": "/owned-volume/_data",
                }
            ],
            "network": "host",
            "state": {"Running": False},
        }
        self.boot = patch.object(
            runtime, "BOOT_FILE", Mock(read_text=lambda: "this-boot")
        )
        self.boot.start()
        self.addCleanup(self.boot.stop)

    def test_matching_owned_resource(self):
        runtime.assert_owned_container(self.container, self.resource)

    def test_rejects_other_container_id(self):
        self.container["id"] = "d" * 64
        with self.assertRaises(AssertionError):
            runtime.assert_owned_container(self.container, self.resource)

    def test_rejects_other_creator_token(self):
        self.container["labels"]["dianzi.creator_token"] = "unknown-token"
        with self.assertRaises(AssertionError):
            runtime.assert_owned_container(self.container, self.resource)

    def test_rejects_other_digest(self):
        self.container["image_id"] = "sha256:wrong-image"
        with self.assertRaises(AssertionError):
            runtime.assert_owned_container(self.container, self.resource)

    def test_rejects_other_mount(self):
        self.container["mounts"][0]["Source"] = "/other-project/_data"
        with self.assertRaises(AssertionError):
            runtime.assert_owned_container(self.container, self.resource)

    def test_rejects_reused_name_creation(self):
        self.container["created"] = "new-creation"
        with self.assertRaises(AssertionError):
            runtime.assert_owned_container(self.container, self.resource)

    def test_rejects_other_boot(self):
        self.resource["boot_id"] = "old-boot"
        with self.assertRaises(AssertionError):
            runtime.assert_owned_container(self.container, self.resource)

    def test_rejects_process_id_reuse(self):
        self.container["state"] = {"Running": True, "Pid": 1234}
        self.resource["container_process"] = {"start_ticks": "old-creation"}
        with (
            patch.object(
                runtime,
                "process_identity",
                return_value={
                    "start_ticks": "new-creation",
                    "cgroup": "0::/dianzi-r01-20261014/owned",
                },
            ),
            self.assertRaises(AssertionError),
        ):
            runtime.assert_owned_container(self.container, self.resource)

    def test_check_does_not_call_docker_stop(self):
        with (
            patch.object(runtime, "OWNED") as owned,
            patch.object(
                runtime, "inspect_container", return_value=copy.deepcopy(self.container)
            ),
            patch.object(runtime, "docker") as docker,
        ):
            owned.__truediv__.return_value.read_text.return_value = runtime.json.dumps(
                self.resource
            )
            result = runtime.stop_owned("identity_selfcheck", check=True)
            self.assertTrue(result["check_only"])
            docker.assert_not_called()

    def test_other_cid_heartbeat_does_not_stop_initial_start(self):
        heartbeat = {
            "container_id": "prior-container",
            "at": "2020-01-01T00:00:00+00:00",
        }
        self.assertIsNone(runtime.heartbeat_failure(self.resource, heartbeat, 1))

    def test_missing_current_cid_heartbeat_stops_after_original_limit(self):
        heartbeat = {
            "container_id": "prior-container",
            "at": "2020-01-01T00:00:00+00:00",
        }
        self.assertEqual(
            runtime.heartbeat_failure(self.resource, heartbeat, 46),
            "guardian_current_heartbeat_missing",
        )

    def test_stale_matching_cid_heartbeat_stops(self):
        self.resource["supervisor"] = {"pid": 12, "start_ticks": "owned"}
        heartbeat = {
            "container_id": self.resource["container_id"],
            "supervisor": self.resource["supervisor"],
            "creator_token": self.resource["creator_token"],
            "generation": self.resource["supervisor"]["start_ticks"],
            "runtime_generation": self.resource["runtime_generation"],
            "at": "2020-01-01T00:00:00+00:00",
        }
        self.assertEqual(
            runtime.heartbeat_failure(self.resource, heartbeat, 1),
            "guardian_heartbeat_stale",
        )

    def test_fake_creator_heartbeat_stops(self):
        self.resource["supervisor"] = {"pid": 12, "start_ticks": "owned"}
        heartbeat = {
            "container_id": self.resource["container_id"],
            "supervisor": self.resource["supervisor"],
            "creator_token": "false-creator",
            "generation": "owned",
            "at": runtime.now().isoformat(),
        }
        self.assertEqual(
            runtime.heartbeat_failure(self.resource, heartbeat, 1),
            "guardian_heartbeat_identity_mismatch",
        )

    def test_expired_deadline_stops_with_fresh_heartbeat(self):
        self.resource["deadline"] = "2020-01-01T00:00:00+00:00"
        heartbeat = {
            "container_id": self.resource["container_id"],
            "at": runtime.now().isoformat(),
        }
        self.assertEqual(
            runtime.heartbeat_failure(self.resource, heartbeat, 1), "guardian_deadline"
        )


if __name__ == "__main__":
    unittest.main()
