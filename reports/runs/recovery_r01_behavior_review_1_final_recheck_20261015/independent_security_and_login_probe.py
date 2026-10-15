"""Fresh synthetic negative inputs and rate regressions; temporary fixtures stay outside reports."""

import contextlib
import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from unittest.mock import patch

candidate = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-recheck-final\dianzi")
sys.path.insert(0, str(candidate))
sys.path.insert(0, str(candidate / "backend/src"))
for name in ("DATABASE_URL", "REDIS_URL", "OPENSEARCH_URL", "AUTH_SECRET_REF", "ALLOWED_ORIGINS"):
    os.environ.pop(name, None)
os.environ["APP_ENV"] = "test"
os.environ["DATA_MODE"] = "fixture"

from fastapi.testclient import TestClient
from scripts import security_scan as scan
from ai_intel.api.app import create_application
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.settings import ApplicationSettings


class ClassificationProbe(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dianzi-independent-classification-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.value = "ReviewFixture" + "Nonce0123456789"
        self.line = "token" + ': "' + self.value + '"'
        self.path = self.root / "reports/runs/controlled/old.log"
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes((self.line + "\n").encode())
        self.table = {"schema_version": 1, "records": []}
        for pattern_id, pattern in scan.PATTERNS.items():
            self.table["records"].append({"path": "reports/runs/controlled/old.log", "raw_sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(), "pattern_id": pattern_id, "pattern_version": 1, "pattern_sha256": hashlib.sha256(pattern.pattern.encode()).hexdigest(), "start": 0, "end": len(self.line), "match_value": self.value, "category": "verified_synthetic_fixture", "fixture_origin": {"source_type": "git", "source_commit": "a" * 40, "source_blob": "b" * 40, "source_path": "frontend/tests/review.test.ts", "source_line": 1, "source_sha256": "c" * 64, "data_mode": "fixture"}, "review_ref": "reports/reviews/review.md"})
        self.table_path = self.root / "reports/security/recovery_fixture_false_positives.json"
        self.table_path.parent.mkdir(parents=True)
        self.save()

    def save(self):
        self.table_path.write_text(json.dumps(self.table), encoding="utf-8")

    def findings(self):
        return scan.scan_repository(self.root, scan.load_fixture_classifications(self.root, self.table_path))

    def test_patterns_roots_suffixes_have_not_weakened(self):
        expected_patterns = {"original_secret_pattern": r"(api[_-]?key|secret[_-]?key|db[_-]?pass|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "original_secret_value_pattern": r"(api[_-]?key|secret[_-]?key|db[_-]?pass|secret|password|passwd|token|jwt)\s*[:=]\s*['\"]([^'\"]{6,})['\"]"}
        self.assertEqual({name: pattern.pattern for name, pattern in scan.PATTERNS.items()}, expected_patterns)
        self.assertEqual(scan.SCAN_ROOTS, ("backend/src", "scripts", "frontend/src", "frontend/dist", "reports/runs"))
        self.assertEqual(scan.SCAN_SUFFIXES, {".py", ".ts", ".tsx", ".js", ".log", ".json", ".html"})

    def test_only_exact_reviewed_spans_are_safe(self):
        self.assertEqual([item.category for item in self.findings()], ["verified_synthetic_fixture"] * 2)
        self.table["records"][0]["start"] += 1
        self.save()
        self.assertIn("unclassified_credential_shape", [item.category for item in self.findings()])

    def test_changed_bytes_same_line_and_adjacent_credentials_are_rejected(self):
        original = self.path.read_bytes()
        extra = "api" + '_key: "' + "Unreviewed" + 'Credential0123456789"'
        for mutation in (original + b"changed\n", (self.line + " " + extra + "\n").encode(), original + (extra + "\n").encode()):
            with self.subTest(size=len(mutation)):
                self.path.write_bytes(mutation)
                self.assertTrue(self.findings())
                self.assertTrue(all(item.category == "unclassified_credential_shape" for item in self.findings()))

    def test_copy_to_new_file_is_not_authorized(self):
        self.path.with_name("copy.log").write_bytes(self.path.read_bytes())
        copied = [item for item in self.findings() if item.path.endswith("copy.log")]
        self.assertEqual(len(copied), 2)
        self.assertTrue(all(item.category == "unclassified_credential_shape" for item in copied))

    def test_unknown_credentials_remain_rejected_in_each_root(self):
        for relative in scan.SCAN_ROOTS:
            with self.subTest(root=relative):
                path = self.root / relative / "new.js"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((self.line + "\n").encode())
                found = [item for item in self.findings() if item.path == path.relative_to(self.root).as_posix()]
                self.assertEqual(len(found), 2)
                self.assertTrue(all(item.category == "unclassified_credential_shape" for item in found))

    def test_escape_and_invalid_metadata_are_rejected(self):
        for path in ("../outside.log", "/outside.log", "reports/../outside.log", "C:/outside.log", "reports\\runs\\old.log", "backend/tests/old.log"):
            with self.subTest(path=path):
                changed = copy.deepcopy(self.table)
                changed["records"][0]["path"] = path
                self.table_path.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaises(scan.ClassificationError):
                    scan.load_fixture_classifications(self.root, self.table_path)
        for field, value in (("pattern_version", 2), ("pattern_sha256", "e" * 64), ("start", True)):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.table)
                changed["records"][0][field] = value
                self.table_path.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaises(scan.ClassificationError):
                    scan.load_fixture_classifications(self.root, self.table_path)
        changed = copy.deepcopy(self.table)
        changed["records"][0]["fixture_origin"]["data_mode"] = "live"
        self.table_path.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(scan.ClassificationError):
            scan.load_fixture_classifications(self.root, self.table_path)

    def test_unicode_and_crlf_coordinates_use_normalized_codepoints_but_hash_raw_bytes(self):
        raw = ("中文\r\n" + self.line + "\r\n").encode()
        self.path.write_bytes(raw)
        for row in self.table["records"]:
            row.update(raw_sha256=hashlib.sha256(raw).hexdigest(), start=3, end=3 + len(self.line))
        self.save()
        self.assertTrue(all(item.category == "verified_synthetic_fixture" for item in self.findings()))
        self.table["records"][0]["start"] = len("中文\r\n".encode())
        self.save()
        self.assertIn("unclassified_credential_shape", [item.category for item in self.findings()])

    def test_exact_value_has_priority_cli_does_not_echo_it_and_missing_input_is_not_completed(self):
        with patch.dict(os.environ, {"DIANZI_REVIEW_SYNTHETIC_EXACT": self.value}):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = scan.main(["--repository-root", str(self.root), "--secret-env", "DIANZI_REVIEW_SYNTHETIC_EXACT"])
            self.assertEqual(result, 1)
            body = json.loads(output.getvalue())
            self.assertEqual(body["exact_scan"], "completed")
            self.assertIn("exact_secret_match", [item["category"] for item in body["findings"]])
            self.assertNotIn(self.value, output.getvalue())
        os.environ.pop("DIANZI_REVIEW_SYNTHETIC_EXACT", None)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = scan.main(["--repository-root", str(self.root), "--secret-env", "DIANZI_REVIEW_SYNTHETIC_EXACT"])
        self.assertEqual(result, 2)
        self.assertEqual(json.loads(output.getvalue())["exact_scan"], "not_run")


class LoginReservationProbe(unittest.TestCase):
    def setUp(self):
        self.origin = "http://127.0.0.1:25173"
        self.passphrase = "Synthetic review " + "passphrase!"
        self.directory = InMemoryUserDirectory()
        self.service = AuthenticationSessionService(self.directory, (self.origin,), False)
        self.service.create_precreated_user("review-user", self.passphrase, "review-tenant", Role.ANALYST)
        self.client = TestClient(create_application(self.service, settings=ApplicationSettings(app_env="test", data_mode="fixture", allowed_origins=(self.origin,))))

    def attempt(self, username="review-user", password=None):
        return self.client.post("/v1/auth/login", json={"username": username, "password": self.passphrase if password is None else password}, headers={"Origin": self.origin})

    def test_six_successful_login_logout_cycles_do_not_consume_failure_window(self):
        codes = []
        for _ in range(6):
            response = self.attempt()
            codes.append(response.status_code)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.post("/v1/auth/logout", headers={"Origin": self.origin, "X-CSRF-Token": response.json()["csrf_token"]}).status_code, 200)
        print({"case": "six-success-login-logout", "codes": codes})

    def test_success_does_not_clear_four_failures(self):
        codes = [self.attempt(password="wrong").status_code for _ in range(4)]
        codes.extend([self.attempt().status_code, self.attempt(password="wrong").status_code, self.attempt(password="wrong").status_code])
        self.assertEqual(codes, [401] * 4 + [200, 401, 429])
        print({"case": "four-failure-success-fifth-failure-cap", "codes": codes})

    def test_eight_parallel_failures_still_have_five_query_entries(self):
        started = Event()
        release = Event()
        guard = Lock()
        count = 0
        actual = self.directory.find_by_username

        def held_lookup(username):
            nonlocal count
            with guard:
                count += 1
                if count == 5:
                    started.set()
            if not release.wait(5):
                raise AssertionError("controlled lookup release missing")
            return actual(username)

        with patch.object(self.directory, "find_by_username", held_lookup), ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(self.attempt, password="wrong") for _ in range(8)]
            try:
                self.assertTrue(started.wait(3))
            finally:
                release.set()
            codes = [future.result(5).status_code for future in futures]
        self.assertEqual(count, 5)
        self.assertEqual(sorted(codes), [401] * 5 + [429] * 3)
        print({"case": "eight-parallel-failures", "codes": codes, "directory_reads": count})

    def test_success_releases_only_itself_while_four_failures_are_inflight(self):
        started = Event()
        release = Event()
        guard = Lock()
        count = 0
        actual = self.directory.find_by_username

        def held_lookup(username):
            nonlocal count
            if username == "held-missing":
                with guard:
                    count += 1
                    if count == 4:
                        started.set()
                if not release.wait(5):
                    raise AssertionError("controlled lookup release missing")
            return actual(username)

        with patch.object(self.directory, "find_by_username", held_lookup), ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(self.attempt, "held-missing", "wrong") for _ in range(4)]
            try:
                self.assertTrue(started.wait(3))
                self.assertEqual(self.attempt().status_code, 200)
                self.assertEqual(self.attempt("fast-missing", "wrong").status_code, 401)
                self.assertEqual(self.attempt("fast-missing", "wrong").status_code, 429)
            finally:
                release.set()
            self.assertEqual([future.result(5).status_code for future in futures], [401] * 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
