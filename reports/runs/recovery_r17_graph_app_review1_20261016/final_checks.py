"""Record final review counts, code protection, and retired process identities."""

import datetime
import hashlib
import json
from pathlib import Path
import subprocess

import psutil

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def main() -> None:
    generated = ROOT / "frontend/tsconfig.tsbuildinfo"
    (RUN / "tsconfig.tsbuildinfo.generated").write_bytes(generated.read_bytes())
    generated.write_bytes(subprocess.check_output(["git", "show", "HEAD:frontend/tsconfig.tsbuildinfo"], cwd=ROOT))
    regression = json.loads((RUN / "regression.json").read_bytes())
    material = json.loads((RUN / "material-audit.json").read_bytes())
    browser = {name: json.loads((RUN / name).read_bytes())["stats"] for name in ["browser-six.json", "browser-independent.json"]}
    known_retired_pids = [30444, 46352, 32088, 42924]
    status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT).decode("utf-8")
    protected_paths = subprocess.check_output(["git", "diff", "--name-only", "HEAD", "--", "frontend", "backend", "contracts", "progress", "tests", "fixtures"], cwd=ROOT).decode("utf-8").splitlines()
    result = {"at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="milliseconds"),
        "regression": {key: regression[key] for key in ["numTotalTests", "numPassedTests", "numFailedTests", "numPendingTests"]},
        "browser": browser, "author_original_counts": material["original_test_counts"],
        "protected_changed_paths": protected_paths, "git_status": status,
        "previous_review_node_pids": {str(pid): psutil.pid_exists(pid) for pid in known_retired_pids},
        "review_listeners": [connection.laddr.port for connection in psutil.net_connections(kind="tcp") if connection.status == "LISTEN" and connection.laddr.port in [25619, 25620]],
        "author_manifest_sha256": material["author_manifest_sha256"], "author_raw_mismatches": material["author_raw_mismatches"],
        "source_git_mismatches": material["source_git_mismatches"], "checkout_lf_mismatches": material["lf_mismatches"],
        "bundle": material["bundle"]}
    (RUN / "final-checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=True, indent=2))
    if protected_paths or result["review_listeners"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
