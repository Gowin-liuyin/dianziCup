"""Apply root-authorized byte preservation only to this run and named raw output files."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

RUN_ROOT = Path(__file__).resolve().parent
WORKTREE = RUN_ROOT.parents[2]
attributes_path = WORKTREE / ".gitattributes"
original_raw = attributes_path.read_bytes()
original_blob = subprocess.check_output(
    ["git", "show", "HEAD:.gitattributes"], cwd=WORKTREE
)
assert original_raw.replace(b"\r\n", b"\n") == original_blob
failure_output = (RUN_ROOT / "final_material_diff_check.stdout.log").read_text(encoding="utf-8")
matches = re.findall(
    r"^(reports/runs/[^\n:]+\.(?:log|xml)):\d+: (trailing whitespace|new blank line at EOF)\.$",
    failure_output,
    re.MULTILINE,
)
reasons = {}
for path, issue in matches:
    assert path.startswith(RUN_ROOT.relative_to(WORKTREE).as_posix() + "/")
    reasons.setdefault(path, set()).add(issue)
reasons[(RUN_ROOT / "final_material_diff_check.stdout.log").relative_to(WORKTREE).as_posix()] = {
    "raw diff-check output echoes the preserved pytest trailing whitespace"
}
assert reasons
rules = [RUN_ROOT.relative_to(WORKTREE).as_posix() + "/** -text"]
rules += [path + " -diff" for path in sorted(reasons)]
attributes_path.write_bytes(original_blob + "\n".encode() + ("\n".join(rules) + "\n").encode())
inventory = {
    "authorization": "root explicitly authorized this run/** -text and named raw output -diff only",
    "old_working_raw_sha256": hashlib.sha256(original_raw).hexdigest(),
    "old_git_blob_sha256": hashlib.sha256(original_blob).hexdigest(),
    "old_normalized_working_equals_blob": True,
    "old_blob_prefix_preserved": attributes_path.read_bytes().startswith(original_blob),
    "rules": rules,
    "diff_files": [{"path": path, "reasons": sorted(reason)} for path, reason in sorted(reasons.items())],
}
(RUN_ROOT / "attribute_adjustment.json").write_text(
    json.dumps(inventory, indent=2) + "\n", encoding="utf-8", newline="\n"
)
report_path = WORKTREE / "reports/tasks/R07-single-model-dimension.md"
with report_path.open("a", encoding="utf-8", newline="\n") as stream:
    stream.write("\n## 精确 raw 材料属性登记\n\n")
    stream.write("root 已明确授权仅本 run/** 的 `-text` 和下列原始工具输出的 `-diff`；未放宽 source/test 或全仓检查。原 Git 属性 blob 完整作为前缀保留。完整前后 hash 与规则见 `attribute_adjustment.json`。\n\n")
    stream.write("| 本 run 内具体文件 | 原始字节保留理由 |\n|---|---|\n")
    for path, reason in sorted(reasons.items()):
        stream.write(f"| `{Path(path).name}` | {', '.join(sorted(reason))} |\n")
print(json.dumps({"exact_diff_files": len(reasons), "old_blob_prefix_preserved": True}))
