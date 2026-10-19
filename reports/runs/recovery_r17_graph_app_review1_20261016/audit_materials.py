"""Independently distinguish frozen Git, raw bytes, and LF text hashes."""

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
AUTHOR = ROOT / "reports/runs/recovery_r17_graph_app_20261016"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main() -> None:
    raw_manifest = (AUTHOR / "artifact_manifest.json").read_bytes()
    manifest = json.loads(raw_manifest)
    rows = []
    for group in ("sourceGit", "materials"):
        for entry in manifest[group]:
            path = entry["path"]
            raw = (ROOT / path).read_bytes()
            blob = git("show", f"164cae93ac888180b056a4c694011402ee387383:{path}")
            lf = raw.replace(b"\r\n", b"\n")
            rows.append({"group": group, "path": path, "raw_sha256": digest(raw),
                "expected_raw_sha256": entry["raw_sha256"], "raw_match": digest(raw) == entry["raw_sha256"],
                "git_sha256": digest(blob), "git_blob": git("rev-parse", f"164cae93ac888180b056a4c694011402ee387383:{path}").decode().strip(),
                "expected_lf_sha256": entry["lf_text_sha256"], "lf_sha256": digest(lf),
                "lf_match": entry["lf_text_sha256"] is None or digest(lf) == entry["lf_text_sha256"],
                "raw_equals_git": raw == blob, "crlf_count": raw.count(b"\r\n"),
                "author_worktree_raw_sha256": digest((Path("D:/wt/r17-graph-app") / path).read_bytes()),
                "author_raw_match": digest((Path("D:/wt/r17-graph-app") / path).read_bytes()) == entry["raw_sha256"],
                "source_git_match": group != "sourceGit" or digest(blob) == entry["git_lf_sha256"]})
    javascript = next((ROOT / "frontend/dist/assets").glob("*.js")).read_text(encoding="utf-8")
    graph_markers = ["证据关系图", "/graph?", "图快照已过期", "r10-graph-1.2.0", "选择此处的关系"]
    fixture_markers = ["合成 Fixture · AI 组件安全事件", "合成厂商公告 · 历史修订", "graph-app-isolated-user",
        "graph-app-fixture-user", "graph-app-fixture-tenant", "graph-app-fixture-a", "graph-app-fixture-b",
        "合成 Fixture · App 事件", "合成 Fixture · 私有 A 旧图", "合成 Fixture · B 当前图"]
    bundle = {"graph_markers": {marker: marker in javascript for marker in graph_markers},
        "fixture_marker_count": sum(javascript.count(marker) for marker in fixture_markers),
        "fixture_markers": {marker: javascript.count(marker) for marker in fixture_markers},
        "sha256": digest(javascript.encode()), "bytes": len(javascript.encode())}
    original_tests = {}
    for filename in ["graph-contract.red.json", "app.red.json", "graph-app-unit.json", "browser.json", "browser.final.json", "browser.release.json"]:
        path = AUTHOR / filename
        if not path.exists():
            original_tests[filename] = "path_not_found"
            continue
        value = json.loads(path.read_bytes())
        original_tests[filename] = value.get("stats", {key: value.get(key) for key in ["numTotalTests", "numPassedTests", "numFailedTests", "numPendingTests"]})
    result = {"author_manifest_sha256": digest(raw_manifest), "expected_manifest_sha256": "7231a79cc2142172dd4c0339483b4100a89fa849ffc7444c2ed7b4c429b97a2b",
        "materials_count": len(manifest["materials"]), "source_count": len(manifest["sourceGit"]),
        "raw_mismatches": [row["path"] for row in rows if not row["raw_match"]],
        "author_worktree_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd="D:/wt/r17-graph-app").decode().strip(),
        "author_raw_mismatches": [row["path"] for row in rows if not row["author_raw_match"]],
        "source_git_mismatches": [row["path"] for row in rows if not row["source_git_match"]],
        "lf_mismatches": [row["path"] for row in rows if not row["lf_match"]],
        "rows": rows, "bundle": bundle, "original_test_counts": original_tests}
    (RUN / "material-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
