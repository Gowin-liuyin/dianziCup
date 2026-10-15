"""Append the independent review repair record while retaining all earlier evidence."""

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
CODE_SHA = "6b7dd7e881bb822e83b55f8302f7aefe565f4940"
INDEPENDENT = Path(
    "D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015/"
    "test_independent_r06_feed_boundaries.py"
)


def clock() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> None:
    started = clock()
    report_path = ROOT / "reports/tasks/R06-feed-parsers.md"
    report = report_path.read_text(encoding="utf-8")
    if "## 修复轮1" in report:
        raise ValueError("repair record already exists")
    files = []
    for path in (
        "backend/src/ai_intel/ingestion/sources/arxiv_atom.py",
        "backend/src/ai_intel/ingestion/sources/trailofbits_rss.py",
        "backend/tests/unit/test_r06_feed_parsers.py",
        "backend/tests/contract/test_r06_archived_feed_replay.py",
    ):
        raw = (ROOT / path).read_bytes()
        blob = subprocess.check_output(["git", "show", f"{CODE_SHA}:{path}"], cwd=ROOT)
        assert raw == blob
        files.append(
            {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        )
    snapshot = {
        "recorded_at": started,
        "repair_base": "8e4d8a0a149980d92f972d510b6d8849298bcadb",
        "code_sha": CODE_SHA,
        "src_tree": "15b19b26f68838fcb62c362f0b7370fc311a1b7b",
        "files": files,
        "independent_fixture_path": str(INDEPENDENT),
        "independent_fixture_sha256": hashlib.sha256(
            INDEPENDENT.read_bytes()
        ).hexdigest(),
        "independent_fixture_edited_by_author": False,
        "index_scope": "this worktree backend/src only",
        "index_cache": "/tmp/dianzi-cbm-r06-feed-parsers-20261015",
        "index_nodes": 1125,
        "index_edges": 5391,
    }
    (RUN / "fix1_code_snapshot.json").write_text(
        json.dumps(snapshot, indent=2), encoding="utf-8"
    )
    labels = [
        "fix1_red_combined",
        "fix1_green_combined",
        "fix1_unit",
        "fix1_combined_recheck",
        "fix1_private_replay",
        "fix1_mypy",
        "fix1_ruff",
        "fix1_format_check",
        "fix1_cbm_index",
        "fix1_cbm_trace_uri",
        "fix1_cbm_arxiv_uri",
        "fix1_cbm_rss_uri",
    ]
    rows = []
    for label in labels:
        entry = json.loads((RUN / f"{label}.json").read_text(encoding="utf-8"))
        count = "N/A"
        if (RUN / f"{label}.xml").exists():
            suites = ElementTree.fromstring(
                (RUN / f"{label}.xml").read_bytes()
            ).findall("testsuite")
            count = ", ".join(
                f"{field}={sum(int(suite.get(field, '0')) for suite in suites)}"
                for field in ("tests", "failures", "errors", "skipped")
            )
        rows.append(
            f"| {label} | {entry['started_at']} / {entry['completed_at']} | "
            f"{entry['exit_code']} | {count} | `{label}.json/.log` |"
        )
    ended = clock()
    report += f"""

## 修复轮1 · 独立初审三类 Must

本轮写作开始：{started}；结束/证据截止：{ended}；首次创建时间保持不变。
作者状态 awaiting_review；三类问题已修复待原独立reviewer定向复核，不签accepted。
独立初审报告：`D:/dianzi/reports/reviews/recovery/G-C-R06-feed-parsers-review-1.md`，原固定8e4候选，结论needs_changes。
本轮代码冻结：`{CODE_SHA}`；src tree `15b19b26f68838fcb62c362f0b7370fc311a1b7b`。本轮4文件与冻结blob字节一致，证据 `fix1_code_snapshot.json`；旧b1ff/8e4结论与记录只对应各自历史版本。

### 确认问题、共同根因与修复

- R06-A-R1-01：total=100/start=0/items=10但仅1entry原来正常返回，遗漏位置1–9可能被后续caller跨过；当前没有产品caller，未声称实际漏采事故。现有范围校验后新增 `len(entries) < min(size,total-start)` 明确失败；保留正常空页、完整页与最终不足一页。新增3种不足页负例；原末页/真实2项Atom继续通过。
- R06-A-R1-02：RSS +1260被stdlib宽松折合+13小时形成确定UTC。先识别时间字段后紧随的数字zone，检查小时≤23/分钟≤59，再复用原stdlib日历/时区换算；不另写日期框架。覆盖正负非法偏移和合法+0000/-0400/+0059/-0001/+2359/GMT；合法 `-0400 (source reference +1260)` 注释不误当时区。缺时间/naive/未来值、Atom UTC-Z检查保持既有语义。
- R06-A-R1-03：原C0检查漏DEL U+007F，RSS输出link及许可原文可含DEL。对arXiv官方URI、许可identifier和RSS官方URI三个既有入口补DEL拒绝，覆盖feed id、entry/PDF、channel/article/GUID、普通许可文本及URI。没有把安全未知许可变成授权，也不改原文/全文状态。PDF/entry原来还受版本/path检查，补共享URI入口以统一边界。

23个新增unit加上原79个作者unit；原47独立例文件未编辑，当前sha256 `{snapshot["independent_fixture_sha256"]}`。原红仍在reviewer初审证据中，本作者另复现17红（独立4 + 新同根因13），未改红例期望/阈值/分母/skip。

### 实际执行与失败保留

| 标签 | 开始 / 结束（Asia/Shanghai） | exit | 原始JUnit事件数 | 参数/日志 |
|---|---|---|---|---|
{chr(10).join(rows)}

纯unit最新1109 passed/0fail/error/skip，6818 statements/2177 missed，coverage68.07%原60门通过；组合1170 passed/0fail/error/skip（unit1109+相关合同14+原独立47），coverage68.32%。mypy84 src、全backend Ruff/208格式通过。零新HTTP/模型调用；仓外私有991606B原RSS20项8断言再次通过，许可unknown完整正文仍未入可推送包。

首次修复后组合`fix1_green_combined`有1169pass/1fail：唯一是未改的原R05 CPU_SECONDS=1忙子进程8秒墙钟TimeoutExpired，初审四红与新增边界均已通过。该失败与先前同类失败均保留；此后同参数pure unit及有限组合复跑通过，**不能说其宿主敏感根因已修复**；已向主控请求诊断，未改timeout、共享代码或skip。

src-only CBM同WT缓存刷新为1125 nodes/5391 edges，not_indexed/partial/unusable=0；源码rg核对所有URI/时间/pagination调用。第一次按短名_official_uri查询返回两个匹配ambiguous（CLI exit0不等于追踪已完成），留档后按实际qualified_name分别追踪两个源成功。不索引私有原件、holdout、报告或秘密；图无产品caller经源码确认，仍不声称真实接线。

### 当前边界与后续

复用原normalizer、stdlib和现有异常，没有新依赖/公共DTO/配置/迁移/锁/进度更改；只有原两parser/原unit和本包证据/报告变化。原artifact hash封存方案保持，最新manifest按原字节重新生成并校验。实现只属内部解析切片：API/worker/PG/UI、真实持续采集/漏采/时效、integration/frontend/e2e/live/manual仍not_run，整R06/T12/T14/G-C不验收。

{ended}：新增本修复记录，保留所有旧红、限额偶发失败和旧版本记录。修订人 `/root/r06_feed_parsers`；原独立reviewer后续定向复核冻结新版本。
"""
    report = re.sub(
        r"^本次写作开始时间：.*$",
        f"本次写作开始时间：{started}",
        report,
        flags=re.MULTILINE,
    )
    report = re.sub(
        r"^本次写作结束时间：.*$",
        f"本次写作结束时间：{ended}",
        report,
        flags=re.MULTILINE,
    )
    report = re.sub(
        r"^最后更新时间：.*$", f"最后更新时间：{ended}", report, flags=re.MULTILINE
    )
    report_path.write_bytes(report.encode("utf-8"))
    print(json.dumps({"report_updated_at": ended, "code_sha": CODE_SHA}))


if __name__ == "__main__":
    main()
