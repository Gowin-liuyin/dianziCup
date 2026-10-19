"""Integrate the independently reviewed hybrid slice without stage promotion."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True, encoding="utf-8").strip()


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


assert git("rev-parse", "HEAD") == "acfe244e93662119b9d4b86033f8903bd4b43ec6"
assert git("branch", "--show-current") == "codex/full-delivery-recovery"
assert git("remote", "get-url", "origin") == "https://github.com/Gowin-liuyin/dianziCup.git"
assert not git("diff", "--cached", "--name-only")
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests", "backend/migrations", "backend/pyproject.toml", "backend/uv.lock", "frontend/src", ".gitattributes")
report = "reports/reviews/recovery/G-D-R12-hybrid-retrieval-review-1-recheck.md"
manifest = "reports/runs/recovery_r12_hybrid_review1_fix1_20261016/review_manifest.json"
assert hashlib.sha256((ROOT / report).read_bytes()).hexdigest() == "fdd7e85122b79c02cd4afc4b0f9a44fbec51322e7761d783920930d9dfb066d8"
assert hashlib.sha256((ROOT / manifest).read_bytes()).hexdigest() == "a66ff50b93bd0763f0b80ae1414655c14a0d31de2393f422da7c1240352dc767"
attributes_hash = hashlib.sha256((ROOT / ".gitattributes").read_bytes()).hexdigest()
user_hash = hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()
argv = ["git", "merge", "--quiet", "--no-ff", "d3f55300c34760bd97d9a85c710fc23b4a480b66", "-m", "G-D integrate reviewed hybrid retrieval final snapshot fence"]
receipt = {"started_at": now(), "before_sha": git("rev-parse", "HEAD"), "reviewed_code_sha": "ba1548d591d2b341e61a230f1cdd5bd387f3235b", "material_sha": argv[4], "review_commit_sha": None, "review_report": report, "argv": argv, "scope": "internal hybrid retrieval slice; 0020/default API/worker/QA not integrated", "stage_accepted": False, "push": "not_run"}
with (RUN / "r12_hybrid_reviewed_merge.log").open("xb") as output:
    result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=90)
receipt["exit_code"], receipt["ended_at"] = result.returncode, now()
receipt["after_sha"] = git("rev-parse", "HEAD")
receipt["root_attributes_unchanged"] = attributes_hash == hashlib.sha256((ROOT / ".gitattributes").read_bytes()).hexdigest()
receipt["user_buildinfo_unchanged"] = user_hash == hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()
(RUN / "r12_hybrid_integration_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
assert result.returncode == 0, "merge failed; retain conflict and inspect"
assert receipt["root_attributes_unchanged"] and receipt["user_buildinfo_unchanged"]
assert not git("diff", "--cached", "--name-only")
print(json.dumps({"head": receipt["after_sha"], "exit_code": result.returncode, "stage_accepted": False, "push": "not_run"}))
