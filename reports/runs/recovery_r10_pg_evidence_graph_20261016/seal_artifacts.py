"""记录代码输入及交付文件的原始字节和 Git 规范 blob；清单自身不自指。"""

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASE = "cc1b1d302e22048f567475b7084bcd5490761ed2"


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def seal():
    head = git("rev-parse", "HEAD").decode().strip()
    code_paths = git("diff", "--name-only", BASE, head, "--", "backend").decode().splitlines()
    code = []
    for path in code_paths:
        raw = (ROOT / path).read_bytes()
        blob = git("cat-file", "blob", head + ":" + path)
        code.append({"path": path, "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_bytes": len(raw), "git_blob_oid": git("rev-parse", head + ":" + path).decode().strip(), "git_blob_sha256": hashlib.sha256(blob).hexdigest(), "git_blob_bytes": len(blob)})
    payload = {"recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "baseline": BASE, "code_commit": head, "files": code}
    (RUN / "frozen_code_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run(["git", "diff", "--binary", BASE, head, "--", "backend"], cwd=ROOT, stdout=(RUN / "frozen_code.patch").open("wb"), check=True)
    paths = [*RUN.iterdir(), ROOT / "reports/tasks/R10-pg-evidence-graph.md"]
    manifest = []
    for path in sorted(paths):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        raw = path.read_bytes()
        relative = path.relative_to(ROOT).as_posix()
        oid = git("hash-object", "-w", "--path=" + relative, relative).decode().strip()
        blob = git("cat-file", "blob", oid)
        manifest.append({"path": relative, "raw_bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(), "git_blob_oid": oid, "git_blob_sha256": hashlib.sha256(blob).hexdigest(), "git_blob_bytes": len(blob)})
    (RUN / "artifact_manifest.json").write_text(json.dumps({"recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "code_commit": head, "files": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"code_commit": head, "code_files": len(code), "artifact_files": len(manifest)}))


if __name__ == "__main__":
    seal()
