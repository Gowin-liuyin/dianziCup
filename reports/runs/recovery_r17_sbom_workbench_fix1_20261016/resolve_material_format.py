"""Preserve the failed material snapshot and change only generated fixture EOF formatting and exact evidence attributes."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
paths = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).splitlines()
prefix = RUN.relative_to(ROOT).as_posix() + "/"
if any(path != "reports/tasks/R17-sbom-workbench-fix1.md" and not path.startswith(prefix) for path in paths):
    raise RuntimeError("staging extends outside the owned fix material")
(RUN / "raw_manifest_before_format_fix.json").write_bytes((RUN / "raw_manifest.json").read_bytes())
subprocess.run(["git", "restore", "--staged", "--", *paths], cwd=ROOT, check=True)
fixture = RUN / "reviewer_fixture.ts"
old = fixture.read_bytes()
new = old.rstrip(b"\r\n") + b"\n"
fixture.write_bytes(new)
if old.rstrip(b"\r\n") != new.rstrip(b"\r\n"):
    raise RuntimeError("fixture semantic content changed")
attrs = RUN / ".gitattributes"
specific = [
    "edge_red_artifacts/reports-runs-recovery_r17_-09e58-n-reference-must-be-revoked/error-context.md",
    "edge_red_artifacts/reports-runs-recovery_r17_-5682e-in-snapshot-must-be-revoked/error-context.md",
]
original_contexts = [{"path": name, "sha256": hashlib.sha256((RUN / name).read_bytes()).hexdigest()} for name in specific]
attrs.write_bytes(attrs.read_bytes() + b"\n" + "".join(name + " -whitespace\n" for name in specific).encode())
now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
receipt = {"changed_at": now, "generated_fixture_only_eof": True, "fixture_before_sha256": hashlib.sha256(old).hexdigest(), "fixture_after_sha256": hashlib.sha256(new).hexdigest(), "non_eof_content_identical": True, "original_error_contexts_raw_unchanged": original_contexts, "root_approved_exact_attribute_paths": specific, "first_material_diff_check_exit": 2, "first_material_diff_raw_log": "material_check_failed.log"}
(RUN / "generated_format_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
report = ROOT / "reports/tasks/R17-sbom-workbench-fix1.md"
body = report.read_text(encoding="utf-8")
body = body.replace(next(line for line in body.splitlines() if line.startswith("最后更新时间：")), "最后更新时间：" + now)
body += f"\n{now} 材料封版格式修订：首staged diff2（854字节原红）为两份Playwright error-context的原摘录行尾空格、生成fixture EOF空行。主控批准仅两个精确MD证据路径-whitespace，原MD bytes/hash未改；fixture只去额外EOF空行，非EOF内容逐字相同，原独审script/所有原断言不改。557/66验证的业务源码18d05、输入与断言均未改变，差异receipt另存；没有重跑无关测试或trim原日志。\n"
report.write_text(body, encoding="utf-8", newline="\n")
print(json.dumps(receipt))
