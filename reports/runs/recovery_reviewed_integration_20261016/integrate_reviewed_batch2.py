"""Integrate frozen reviewed product slices without overwriting separately sealed evidence."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASELINE = "6be1d1b2f2101bea58b488531dbfb1f83fcdc0ce"
PACKAGES = (
    ("sbom_real_browser", "4a17fa3fb7357a8c2b9d647f62c875958a24a27d", ("frontend",), "D:/wt/r17-real-sbom-browser-review1/reports/reviews/recovery/G-E-R17-integrated-sbom-browser-review-1.md", "70aed583674be26ea4a26e2ac2f610ab6275193a33f6a9b37ac61434e8ba514c"),
    ("conversation_context", "eb030458009812ec037928e4bc2f1a4cdbe64c46", ("backend/src/ai_intel/answering", "backend/tests/unit/*conversation*", "backend/tests/integration/*conversation*"), "D:/wt/r12-conversation-context-review1-fix1/reports/reviews/recovery/G-D-R12-conversation-context-review-1-recheck.md", "022e4958898fde5d6a6359adb873931ca4db77429147453c14e0cc73d607b1dd"),
    ("forward_0023_0026", "16484eaca45791ed2ec403471561faa10ab6d036", ("backend/migrations", "backend/tests/contract/test_recovery_forward_migrations_0023_0026.py", "backend/tests/integration/test_recovery_forward_migrations_0023_0026_pg.py"), "D:/wt/recovery-forward-migrations-review1/reports/reviews/recovery/G-D-recovery-forward-migrations-review-1.md", "86d86030818cfeaa99704892c4b34bc8f6f4e35df35c3d4c3f7bc17d0cea6bd8"),
    ("enrichment_input_audit", "648c71795e1bea34511ec0d04348f35f6463a5e6", ("backend/src/ai_intel/enrichment/job_contracts.py", "backend/src/ai_intel/enrichment/job_models.py", "backend/src/ai_intel/enrichment/job_service.py", "backend/tests/*/*input_audit*"), "D:/wt/r07-input-audit-review1-fix1/reports/reviews/recovery/G-C-R07-input-audit-review-1-recheck.md", "f1ff0621dfbcab9c4ceb79d8f23d836ddc9a22ebe409635a4838c97ecdd93d0e"),
    ("api_key_credentials", "8e0485231bf9367d5b4b3a79802bdf346b1fb745", ("backend/src/ai_intel/api/credentials.py", "backend/src/ai_intel/api/credential_models.py", "backend/tests/*/*api_key*", "backend/tests/security/credential_failure_probe.py"), "D:/wt/r18-api-key-review1-fix2/reports/reviews/recovery/G-E-R18-api-key-credential-review-1-recheck2.md", "74a4fe0f783f2a466218e29792af16b5098511eabfd586b7951f072897fce0b8"),
    ("mcp_complete_output_budget", "c691a0d5d0e06a4cc52567e1e816cd49cb0b1e7f", ("sdk/python",), "D:/wt/r18-mcp-output-budget-review1-fix1/reports/reviews/recovery/G-E-R18-mcp-output-budget-review-1-recheck.md", "3377b1fe0992262b914b3e103a8327eced6bc1787d5fdb1255065082629f9733"),
)


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, timeout=120)


assert git("rev-parse", "HEAD").decode().strip() == BASELINE
assert not git("diff", "--cached", "--name-only").strip()
assert not git("status", "--porcelain", "--", "backend", "frontend/src", "frontend/e2e", "sdk", "contracts", ".gitattributes").strip()
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
protected_sha = hashlib.sha256(protected.read_bytes()).hexdigest()
assert protected_sha == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
receipt_path = RUN / "source_integration_batch2_receipt.json"
assert not receipt_path.exists()
receipt = {"started_at": clock(), "baseline": BASELINE, "stage_accepted": False, "push": "not_run", "mode": "reviewed_source_only", "packages": []}


def save():
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")


for name, target, prefixes, report_name, report_sha in PACKAGES:
    report = Path(report_name)
    assert hashlib.sha256(report.read_bytes()).hexdigest() == report_sha
    before = git("rev-parse", "HEAD").decode().strip()
    base = git("merge-base", before, target).decode().strip()
    files = git("diff", "--name-only", base, target, "--", *prefixes).decode().splitlines()
    assert files and "frontend/tsconfig.tsbuildinfo" not in files
    assert all(path.startswith(("backend/", "frontend/", "sdk/")) for path in files)
    patch = git("diff", "--binary", base, target, "--", *files)
    (RUN / ("batch2_" + name + ".patch")).write_bytes(patch)
    item = {"name": name, "before": before, "base": base, "reviewed_source": target, "files": files, "review_report": str(report), "review_report_sha256": report_sha, "patch_sha256": hashlib.sha256(patch).hexdigest(), "started_at": clock()}
    receipt["packages"].append(item)
    save()
    for label, arguments, data in (("apply", ["apply", "--index", "--binary", "-"], patch), ("staged_check", ["diff", "--cached", "--check"], None)):
        with (RUN / ("batch2_" + name + "_" + label + ".log")).open("xb") as output:
            result = subprocess.run(["git", *arguments], input=data, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120, check=False)
        item[label + "_exit_code"] = result.returncode
        save()
        assert result.returncode == 0
    assert set(files) == set(git("diff", "--cached", "--name-only").decode().splitlines())
    assert all(git("show", ":" + path) == git("show", target + ":" + path) for path in files)
    with (RUN / ("batch2_" + name + "_commit.log")).open("xb") as output:
        result = subprocess.run(["git", "-c", "gc.auto=0", "commit", "-m", "Recovery checkpoint integrate independently reviewed " + name.replace("_", " ")], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120, check=False)
    item["commit_exit_code"] = result.returncode
    save()
    assert result.returncode == 0
    item.update(integrated_sha=git("rev-parse", "HEAD").decode().strip(), ended_at=clock(), reviewed_git_blobs_exact=True)
    assert hashlib.sha256(protected.read_bytes()).hexdigest() == protected_sha
    save()
    print(json.dumps({"package": name, "sha": item["integrated_sha"], "files": len(files)}), flush=True)
receipt["ended_at"] = clock()
save()
