"""Seal reviewer-owned receipts without touching shared implementation or status."""

import hashlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import psutil

ROOT = Path(__file__).resolve().parent
WORKTREE = Path("C:/Users/yinha/.codex/worktrees/r05-semantic-independent-review/dianzi")
CACHE = Path("C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=WORKTREE, text=True).strip()


def main():
    results = {}
    for path in ROOT.glob("*.xml"):
        suite = ElementTree.parse(path).getroot()
        if suite.tag == "testsuites":
            suite = list(suite)[0]
        results[path.name] = {name: suite.attrib.get(name) for name in
                             ("tests", "failures", "errors", "skipped", "time")}
    weights = []
    for folder in ("e5", "mmarco"):
        for name in ("onnx/model.onnx", "tokenizer.json", "config.json"):
            path = CACHE / folder / name
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            weights.append({"relative_path": f"{folder}/{name}", "bytes": path.stat().st_size,
                            "sha256": digest})
    processes = []
    for process in psutil.process_iter(["pid", "ppid", "name", "cmdline"]):
        try:
            arguments = process.info["cmdline"] or []
            joined = " ".join(arguments).replace("\\", "/").lower()
            if "r05-semantic-independent-review" in joined:
                processes.append({key: process.info[key] for key in ("pid", "ppid", "name")})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    snapshot = {"review_sha": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
                "baseline_sha": git("rev-parse", "31c2866"),
                "helper_sha": git("rev-parse", "77add60"), "git_status": git("status", "--short"),
                "diff_check": subprocess.run(["git", "diff", "--check", "31c2866", "HEAD"],
                                             cwd=WORKTREE, check=False).returncode,
                "python": sys.version,
                "versions": {name: importlib.metadata.version(name) for name in
                             ("onnxruntime", "tokenizers", "numpy", "psutil", "pytest")},
                "test_results": results, "model_files": weights,
                "matching_review_processes": processes}
    destination = sys.argv[1] if len(sys.argv) > 1 else "final_snapshot.json"
    (ROOT / destination).write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(json.dumps(snapshot, ensure_ascii=False))


if __name__ == "__main__":
    main()
