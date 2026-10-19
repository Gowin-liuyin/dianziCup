"""Keep the failed material checkpoint and close its documentation whitespace defect."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/tasks/R06-revision-mode-fixture-body-fix.md"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
harness = RUN / "run_checks.py"
before = harness.read_bytes()
harness.write_bytes(before.rstrip() + b"\n")
text = REPORT.read_text(encoding="utf-8")
rows = text.splitlines()
text = "\n".join(
    label + "：" + started
    if row.startswith(label + "：")
    else row
    for row in rows
    for label in (next((name for name in ("本次写作开始时间", "本次写作结束时间", "最后更新时间", "证据截止时间") if row.startswith(name + "：")), "unused"),)
) + "\n"
text += f"""

{started}，作者：保留材料checkpoint a0acd09668660adbf96572888dbcfdf14b4e5194。prepare_material 的 staged diff check 发现 own run_checks.py:149 末尾额外空行，exit2；外层 PowerShell未因该非零返回停止，随后错误执行了材料commit。该问题是作者命令控制错误；不改变 source6bb或测试结论。此轮仅删除取证脚本额外EOF空行，重新封存文件raw/Git身份，Python check=True顺序阻止失败后commit。旧manifest及失败checkpoint不覆写，初次创建时间保留，不称旧材料检查通过。
"""
REPORT.write_text(text, encoding="utf-8")
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
REPORT.write_text(REPORT.read_text(encoding="utf-8").replace("本次写作结束时间：" + started, "本次写作结束时间：" + ended), encoding="utf-8")
files = [REPORT, harness, Path(__file__)]
manifest = RUN / "material_repair_identity.json"
manifest.write_text(json.dumps({
    "writing_started": started,
    "writing_ended": ended,
    "failure_checkpoint": "a0acd09668660adbf96572888dbcfdf14b4e5194",
    "original_harness_sha256": hashlib.sha256(before).hexdigest(),
    "files": [{"path": path.relative_to(ROOT).as_posix(), "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in files],
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
files.append(manifest)
subprocess.run(["git", "add", "--", *[path.relative_to(ROOT).as_posix() for path in files]], cwd=ROOT, check=True, timeout=10)
subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True, timeout=10)
assert subprocess.check_output(["git", "diff", "6bb19fcdbf5c8242142c3f61e338b98a29bc5501", "--", "backend"], cwd=ROOT, timeout=10) == b""
subprocess.run(["git", "commit", "-m", "docs(R06): close material whitespace guard failure"], cwd=ROOT, check=True, timeout=10)
print(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=10).decode().strip())
