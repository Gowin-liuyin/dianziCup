"""以Git实际blob字节封存本次有限交付，并验证提交字节一致性。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
BASE_SHA = "bde7497b3b67b96da0af63e85b197931858a8ca7"
CODE_SHA = "2e1f5029a8e153bdd8289ac20b67e50d51e30bca"
REPORT_PATH = "reports/tasks/R13-fofa-relay-config-fix1.md"
BUSINESS_PATHS = [
    "backend/src/ai_intel/assets/fofa_relay.py",
    "backend/tests/contract/test_r13_fofa_relay_account_wire.py",
]
MANIFEST_PATH = RUN / "artifact_manifest.json"


def git_bytes(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=WORKTREE)


def main() -> None:
    if len(sys.argv) > 1:
        revision = sys.argv[1]
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        for artifact in manifest["artifacts"]:
            body = git_bytes("show", f"{revision}:{artifact['path']}")
            assert hashlib.sha256(body).hexdigest() == artifact["sha256"], artifact[
                "path"
            ]
            assert len(body) == artifact["bytes"], artifact["path"]
            assert (
                git_bytes("rev-parse", f"{revision}:{artifact['path']}")
                .decode()
                .strip()
                == artifact["git_blob_oid"]
            )
        print(
            json.dumps(
                {"revision": revision, "verified_artifacts": len(manifest["artifacts"])}
            )
        )
        return
    paths = [WORKTREE / path for path in BUSINESS_PATHS + [REPORT_PATH]]
    paths.extend(
        path for path in RUN.iterdir() if path.is_file() and path != MANIFEST_PATH
    )
    artifacts = []
    for path in sorted(paths):
        relative_path = path.relative_to(WORKTREE).as_posix()
        body = git_bytes("show", f":{relative_path}")
        assert body == path.read_bytes(), relative_path
        artifacts.append(
            {
                "path": relative_path,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "git_blob_oid": git_bytes("rev-parse", f":{relative_path}")
                .decode()
                .strip(),
            }
        )
    manifest = {
        "task": "R13-fofa-relay-config-fix1",
        "status": "awaiting_review",
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "base_sha": BASE_SHA,
        "code_sha": CODE_SHA,
        "byte_source": "Git index blobs; workspace bytes asserted equal",
        "self_exclusion": "artifact_manifest.json is excluded to avoid a recursive digest",
        "artifacts": artifacts,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "code_sha": CODE_SHA,
                "artifact_files": len(artifacts),
                "manifest_sha256": hashlib.sha256(
                    MANIFEST_PATH.read_bytes()
                ).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
