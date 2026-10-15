"""Record the second timezone-boundary repair without overwriting earlier failed evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
CODE_SHA = "9138e1741722491ca0c4df6b5540b76157a2b47e"


def main() -> None:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    path = ROOT / "reports/tasks/R06-feed-parsers.md"
    report = path.read_text(encoding="utf-8")
    if "## 修复轮2" in report:
        raise ValueError("repair record already exists")
    file_paths = [
        "backend/src/ai_intel/ingestion/sources/arxiv_atom.py",
        "backend/src/ai_intel/ingestion/sources/trailofbits_rss.py",
        "backend/tests/unit/test_r06_feed_parsers.py",
        "backend/tests/contract/test_r06_archived_feed_replay.py",
    ]
    files = []
    for file_path in file_paths:
        raw = (ROOT / file_path).read_bytes()
        assert raw == subprocess.check_output(
            ["git", "show", f"{CODE_SHA}:{file_path}"], cwd=ROOT
        )
        files.append(
            {
                "path": file_path,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        )
    independent_files = [
        Path(
            "D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/test_independent_r06_feed_boundaries.py"
        ),
        Path(
            "D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_recheck_20261015/test_timezone_repair_boundary.py"
        ),
    ]
    snapshot = {
        "recorded_at": started,
        "base_sha": "cb9e3c53f5504b7c6ed3b65e40ba0b92c124fd9f",
        "code_sha": CODE_SHA,
        "src_tree": "d7ba58c14999c79a01fe4d732235d5035a69793a",
        "files": files,
        "index_scope": "this worktree backend/src only",
        "index_nodes": 1126,
        "index_edges": 5394,
        "python_boundary": "locked Python >=3.12,<3.13",
        "independent_unmodified_inputs": [
            {"path": str(item), "sha256": hashlib.sha256(item.read_bytes()).hexdigest()}
            for item in independent_files
        ],
    }
    (RUN / "fix2_code_snapshot.json").write_text(
        json.dumps(snapshot, indent=2), encoding="utf-8"
    )
    rows = []
    for label in (
        "fix2_red_combined",
        "fix2_combined",
        "fix2_unit",
        "fix2_mypy",
        "fix2_ruff",
        "fix2_format_check",
        "fix2_private_replay",
        "fix2_cbm_index",
        "fix2_cbm_timezone",
    ):
        entry = json.loads((RUN / f"{label}.json").read_text(encoding="utf-8"))
        counts = "N/A"
        if (RUN / f"{label}.xml").exists():
            suites = ElementTree.fromstring(
                (RUN / f"{label}.xml").read_bytes()
            ).findall("testsuite")
            counts = ", ".join(
                f"{field}={sum(int(suite.get(field, '0')) for suite in suites)}"
                for field in ("tests", "failures", "errors", "skipped")
            )
        rows.append(
            f"| {label} | {entry['started_at']} / {entry['completed_at']} | {entry['exit_code']} | {counts} | `{label}.json/.log` |"
        )
    ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    report += f"""

## 修复轮2 · 数字时区的共同解析边界

本轮写作开始：{started}；结束/证据截止：{ended}；首次创建时间保持不变。
作者状态 awaiting_review；原Must1/3在独立cb9复核已closed，本轮只修原Must2未关闭边界；没有签accepted、push或API/PG接线。
原独立复核报告：`D:/dianzi/reports/reviews/recovery/G-C-R06-feed-parsers-review-1-recheck.md`（cb9候选needs_changes）。`07:00:0 +1260`与`7:0:0 +1260`原2红未编辑；本作者新增13个同根因非法输入和13个合法对应输入，预期不从实现生成。

根因：第1轮数字zone检查仍依赖固定clock位数，而锁定Python3.12的stdlib接受更宽时钟拼写、附着offset、RFC850及部分ctime排列。不是新的来源事故，未声称真实上游已有该输入/实际指标受损。

修复：删除clock正则；新增私有`_timezone_token`只按实际标准库字段消费位置定位原始zone（可选weekday/逗号、RFC850日期拆分、附着zone、ctime字段交换），不解释日历或时钟。对实际数值zone使用相同int接受语义检查绝对HH≤23/MM≤59后，原`parsedate_to_datetime`完成日历/timezone/UTC转换。非数字GMT等仍交原库；-0000仍按原库未知zone拒绝；缺时间仍None。这里只补stdlib未校验原HH/MM的信任边界，没有私有stdlib运行时import或通用日期框架。

26个新增case覆盖短clock、无秒、点分、宽零填充、附着offset、RFC850/ctime、weekday无FWS、数字zone无sign/int下划线/Unicode、Unicode时钟；合法注释和尾部忽略token含+1260不误拒绝，未来RFC850年2060也不误当zone。支持范围仍是本项目锁定Python3.12布局；依赖升级若改变该消费布局须复核这些合同，而不是把原子串特判扩成另一日期解释器。

代码冻结：`{CODE_SHA}`；src tree `d7ba58c14999c79a01fe4d732235d5035a69793a`。只改原RSS parser/直接unit；arXiv、公共文件、DTO、配置、迁移、锁、认证、进度和所有独立期望不变。四业务/测试文件与冻结blob字节一致，见 `fix2_code_snapshot.json`；旧b1ff/6b7/cb9意见仅对应其历史版本，未覆盖其失败记录。

| 标签 | 开始 / 结束（Asia/Shanghai） | exit | JUnit事件数 | 参数/日志 |
|---|---|---|---|---|
{chr(10).join(rows)}

先复现1198集合中的15红（原2+新增13）/1183通过，日志保留；修复后1198 passed/0fail/error/skip，coverage68.45%（6852 statements/2162 missed），原60门不变。最新pure unit1135 passed/0fail/error/skip，coverage68.20%（2179 missed）；包含原1135 unit + 14相关合同 + 47原独立边界 + 2新独立边界的组合如上。84 src mypy、全backend Ruff、208格式通过，原CPU_SECONDS=1/timeout=8用例本轮两次通过，旧偶发失败未删且不宣称根因已修复，没有进一步扩大重跑。

原公有arXiv2篇/明确RSS metadata-only20项随合同再次通过；仓外991606B完整原RSS20项8断言再次通过、零网络、未知许可全文不进公开包。原47+新2独立输入文件路径/hash由snapshot记录，作者未修改。索引仅本WT src、外部同缓存刷新1126 nodes/5394 edges，not_indexed/partial/unusable=0，trace+rg核对唯一caller `_published_at`；新增helper没有API/worker caller。复用stdlib/既有normalizer，没有新依赖。

实现仍仅内部parser；integration/frontend/e2e/live/manual均not_run，整R06/T12/T14/G-C不验收。本轮待原独立reviewer在新冻结候选复核Must2；若同根因再失败，由主控新诊断Agent处理，作者不继续扩大补丁。

{ended}：追加修复轮2及真实红→绿、合法形态保护、版本绑定与未验证范围。修订人 `/root/r06_feed_parsers`。
"""
    for name, value in (
        ("本次写作开始时间", started),
        ("本次写作结束时间", ended),
        ("最后更新时间", ended),
    ):
        report = re.sub(
            rf"^{name}：.*$", f"{name}：{value}", report, flags=re.MULTILINE
        )
    path.write_bytes(report.encode("utf-8"))
    print(json.dumps({"updated_at": ended, "code_sha": CODE_SHA}))


if __name__ == "__main__":
    main()
