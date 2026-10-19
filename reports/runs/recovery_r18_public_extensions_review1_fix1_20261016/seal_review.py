"""Seal the bounded recheck and copy only its authorized artifacts to the controller."""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
MAIN = Path("D:/dianzi")
REPORT = ROOT / "reports/reviews/recovery/G-E-R18-public-extensions-review-1-recheck.md"
CODE = "831c61f5c82d663434172a258bbd0c85757a6567"
LOCAL_TIME = timezone(timedelta(hours=8))


def digest(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest()}


identity = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=False)
tracked = subprocess.run(["git", "diff", "--exit-code"], cwd=ROOT, capture_output=True, check=False)
if identity.returncode or identity.stdout.decode().strip() != CODE or tracked.returncode:
    raise RuntimeError("Frozen code identity or tracked content changed")
commands = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(RUN.glob("*.command.json"))]
(RUN / "commands.json").write_text(json.dumps(commands, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
manifest = {
    "schema_version": 1, "review_id": "G-E-R18-public-extensions-review-1-recheck",
    "reviewer": "/root/r18_public_extensions_first_independent_review",
    "reviewed_code_sha": CODE, "baseline_code_sha": "456320b6c78e2936fd9f9767724ec3eb17f5c88b",
    "verdict": "ship_public_contract_slice_only", "closed_must": ["initial review Must1"],
    "worktree": str(ROOT), "branch": "codex/r18-public-extensions-review1-fix1",
    "report_first_written_at": datetime.fromtimestamp(REPORT.stat().st_ctime, LOCAL_TIME).isoformat(),
    "sealed_at": datetime.now(LOCAL_TIME).isoformat(), "report": digest(REPORT),
    "schema_git_blob_sha256": "4ccc4337586137a407359a1c4a59dc5d92081a2f4b50ee32cc53fac16095d50b",
    "physical_pg_requests": 0, "paid_calls": 0, "downloads": 0,
    "allowed_next_work": "Synchronize material digest; implement opt-in producer/SDK/MCP against shared PG and typed semantic gates, then independently review frozen runtime. This does not accept whole R18/G-E or validate output budget.",
    "frozen_input_files": [digest(ROOT / path) for path in (
        "contracts/schemas/public_api_extensions_v1.json", "contracts/schemas/public_api_v2.json",
        "backend/tests/contract/test_r18_public_extensions.py", "backend/tests/contract/test_r18_task_poll_uri.py",
        "docs/decisions/CR-R18_public_envelopes_and_output_budget.md", "reports/tasks/R18-public-envelopes-output-budget.md",
    )],
    "files": [digest(path) for path in sorted(RUN.iterdir()) if path.is_file() and path.name != "manifest.json"],
}
(RUN / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
target_report = MAIN / REPORT.relative_to(ROOT)
target_run = MAIN / RUN.relative_to(ROOT)
if target_report.exists() or target_run.exists():
    raise RuntimeError("Controller output already exists; refuse overwrite")
target_report.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(REPORT, target_report)
shutil.copytree(RUN, target_run)
for item in [manifest["report"], *manifest["files"]]:
    if hashlib.sha256((MAIN / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
        raise RuntimeError("Copied digest mismatch")
print(json.dumps({"sealed_at": manifest["sealed_at"], "report_sha256": manifest["report"]["sha256"],
                  "report": str(target_report), "manifest": str(target_run / "manifest.json"),
                  "file_count_excluding_manifest": len(manifest["files"]), "copied_digests_verified": True},
                 ensure_ascii=False, indent=2))
