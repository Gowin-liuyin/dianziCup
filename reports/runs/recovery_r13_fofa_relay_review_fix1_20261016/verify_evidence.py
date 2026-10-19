"""以固定Git blob校核作者清单，保持原始证据只读。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
HEAD = "9dfefa47183757aec0414cf701f4d4698827ff78"


def blob(path: str, revision: str = HEAD) -> bytes:
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=WORKTREE)


def main() -> None:
    manifests = []
    for folder in ("recovery_r13_fofa_relay_config_20261015", "recovery_r13_fofa_relay_config_fix1_20261016"):
        path = f"reports/runs/{folder}/artifact_manifest.json"
        raw = blob(path)
        manifest = json.loads(raw)
        mismatch = []
        checkout_differences = []
        for item in manifest["artifacts"]:
            revision = manifest["code_sha"] if item["path"].startswith(("backend/", "config/")) else HEAD
            content = blob(item["path"], revision)
            if len(content) != item["bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
                mismatch.append(item["path"])
            if (WORKTREE / item["path"]).read_bytes() != content:
                checkout_differences.append({"path": item["path"], "compared_revision": revision})
        digest = hashlib.sha256(raw).hexdigest()
        if "fix1" in folder:
            assert digest == "0ef8cb1d3c685096ca0edd760830dd397603cc7308f7ba250092d41564409b96"
            assert len(manifest["artifacts"]) == 62
        assert not mismatch, mismatch
        manifests.append({"path": path, "sha256": digest, "artifacts": len(manifest["artifacts"]), "git_blob_mismatches": mismatch, "checkout_byte_differences": checkout_differences})
    previous = Path("D:/wt/r13-fofa-relay-review-1/reports/runs/recovery_r13_fofa_relay_review_1_20261016")
    originals = []
    for name in ("test_independent_relay_boundaries.py", "independent_boundaries.log", "independent_boundaries.xml"):
        raw = (previous / name).read_bytes()
        originals.append({"path": str(previous / name), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    result = {"head_sha": HEAD, "manifests": manifests, "previous_raw_read_only": originals}
    (RUN / "author_artifact_verification_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
