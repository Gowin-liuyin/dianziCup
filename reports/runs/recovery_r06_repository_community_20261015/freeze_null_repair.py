"""Record the null-array repair without altering the initial frozen evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
ZONE = timezone(timedelta(hours=8))
CODE_SHA = "d4e22fab7ad4be7bb6281d5d8dd9db3ea53729a6"
REPAIR_BASELINE = "5e952f25d7a1c03296e1a8801a757c9c0317af99"
INDEPENDENT_PROBE = Path(
    "D:/wt/r06-repos-review/reports/runs/recovery_r06_repository_community_review_1_20261015/test_independent_boundaries.py"
)


def main() -> int:
    receipt_path = RUN / "null_fix_provenance.json"
    if receipt_path.exists():
        raise RuntimeError("This repair has already been frozen")
    started = datetime.now(ZONE).isoformat(timespec="seconds")
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip() == CODE_SHA
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=WORKTREE, text=True).strip()
    probe = INDEPENDENT_PROBE.read_bytes()
    (RUN / "null_fix_independent_boundaries.original.py").write_bytes(probe)
    labels = ("null_independent_red", "null_fixed_regression", "null_mypy", "null_ruff", "null_format")
    commands = [json.loads((RUN / f"{label}.command.json").read_bytes()) for label in labels]
    counts = []
    for label in labels[:2]:
        suites = list(ET.parse(RUN / f"{label}.junit.xml").getroot().iter("testsuite"))
        counts.append(
            {"label": label, **{
                field: sum(int(suite.get(field, "0")) for suite in suites)
                for field in ("tests", "failures", "errors", "skipped")
            }}
        )
    assert counts[0]["tests"] == counts[0]["failures"] == 7
    assert counts[1] == {"label": "null_fixed_regression", "tests": 1250, "failures": 0, "errors": 0, "skipped": 0}
    assert all(record["exit_code"] == 0 for record in commands[1:])
    command_rows = ["| label | 实际起止（Asia/Shanghai） | exit |", "|---|---|---|"]
    for label, record in zip(labels, commands, strict=True):
        command_rows.append(f"| {label} | {record['started_at']} / {record['ended_at']} | {record['exit_code']} |")
    report = WORKTREE / "reports/tasks/R06-repository-community.md"
    content = report.read_text(encoding="utf-8")
    content = content.replace("候选代码 SHA：e5b48ae", "初次候选代码 SHA：e5b48ae", 1)
    content = content.replace("代码 tree：ac960dc", "初次代码 tree：ac960dc", 1)
    content = content.replace(
        "独立审查：待主控新建 reviewer；本作者未作验收签字，也未 push。",
        "独立初审：G-C-R06-repository-community-review-1.md 判 needs_changes；Must1 已自检修复，待原独立 reviewer 定向复核。本作者未作验收签字、未 push。",
        1,
    )
    content = content.replace("最终自动验收：1212 pass", "初次候选自动自检：1212 pass", 1)
    content = content.replace("候选测试在业务内容冻结前运行", "初次候选测试在业务内容冻结前运行", 1)
    ended = datetime.now(ZONE).isoformat(timespec="seconds")
    section = f"""

## 8. 修复轮1 · 独立 Must1 的显式 null 数组

本次写作开始时间：{started}；结束时间：{ended}。
修复基线：{REPAIR_BASELINE}；修复代码 SHA：{CODE_SHA}；tree：{tree}。
当前作者状态仍 awaiting_review，Must1 为已自检修复/待独立复核；不签 accepted。当前验证增加至下列实际结果，初次1212及初审7红属于保留的历史快照。

独立初审报告 `reports/reviews/recovery/G-C-R06-repository-community-review-1.md` 于2026-10-15T18:56:11+08:00确认一个共同根因：_string_tuple/_objects 的 None 默认值吞掉 aliases/related/upstream/affected/ranges/events/versions 显式null。最小输入 `{{"id":"OSV-REVIEW","affected":[{{"ranges":[{{"type":"SEMVER","events":null}}]}}]}}` 在5e952返回空事件且 unsupported_scheme=false，预期 OsvContractError。本作者先直接复跑 reviewer 原文件的七条拒绝断言，实际7 fail/18 deselected/exit1，未将错误改成skip。

修复范围仅 osv.py 与既有 test_r06_osv_range_boundaries.py。两个 helper 只接受 list；全部七处缺省 caller 显式 `.get(field, [])`，故缺键行为兼容，显式null被类型边界拒绝。bounded_package_query 是 _objects 的另一caller，已有结果list检查保留；任何坏条目仍整批报错。没有公共schema/数据/金标/阈值/依赖/锁/产品接线变更。

新增13个作者测试包括七种显式null、顶层缺键、嵌套缺键、显式空数组及SEMVER/GIT/FUTURE第二分支的null失败；缺失信息保留raw，未伪造版本或边界，也未把空范围推成资产安全。独立25项原文件未改，来自 `{INDEPENDENT_PROBE.as_posix()}`；原字节副本 `null_fix_independent_boundaries.original.py` 及 sha256 在 provenance 中，复跑使用原冻结 reviewer 文件，其真实样本仍取 reviewer WT 内的同一5e952正文。

{chr(10).join(command_rows)}

全量本轮1250 pass/0 fail/0 error/0 skip =1102 unit +15旧/真实样本contract +108 network security +25独立边界。coverage70.83%（6818 statements/1989 missed），原60门完整保留；现有R05真实native CPU限额本轮也通过，无降超时/重试/删例。mypy84源文件无问题，两个改动文件Ruff/format通过。仅既有StarletteDeprecationWarning。所有命令精确argv/cwd/起止/exit及JUnit留 run；shared runner 的 baseline_sha 仍是原项目1ff5496，本轮修复基线另明确记录5e952，未误称它为当前待审代码。

修复前 `_objects` 图与全src/tests rg 已核对；候选索引 `dianzi_r06_repos_d4e22fa` 对应此代码，1103节点/5321边，0 not_indexed/partial/unusable。索引仍只backend/src，缓存仓外；_objects 两caller为 normalize_osv_record/bounded_package_query，_string_tuple 仅normalizer，全七个调用处已源码交叉核对。schema、前后trace与caller日志名以null_fix开头，无使用旧图审新代码。

初始5e952原文、真实样本、gzip和旧证据seal全部不改；初始 evidence_commit_inventory.json 描述5e952快照，旧报告hash须对该commit核验，本轮更新报告由新的null_fix_provenance/inventory描述，不能将旧snapshot清单误当当前报告hash。首次报告创建时间保留。本轮没有任何新公开/付费网络请求、秘密读取、holdout或产品live；integration/frontend/e2e/live/manual仍未跑，剩余接线限制保持第6节。

元数据命令有一次 PowerShell 未给 HEAD^{{tree}} 加引号导致git参数错误，仅树号查询失败；随后用引号与subprocess argv array正确读得上述tree，未改代码、测试或把旧tree冒充当前版本。后续工具/审查以 provenance 的真实code/tree为准。

文档修订：{ended}，作者记录独立Must1、七红/修复/1250实际结果与新冻结索引；旧失败没有覆盖。下一步原独立reviewer在新完整候选上定向复核后，由主控决定是否合并；整R06/T11/T13/G-C仍不因此验收。
"""
    for field in ("本次写作开始时间",):
        content = re.sub(field + r"：[^\n]+", field + "：" + started, content, count=1)
    for field in ("本次写作结束时间", "最后更新时间", "本报告证据截止时间"):
        content = re.sub(field + r"：[^\n]+", field + "：" + ended, content, count=1)
    report.write_text(content + section, encoding="utf-8")
    record = {
        "created_at": ended, "code_sha": CODE_SHA, "code_tree": tree,
        "repair_baseline": REPAIR_BASELINE, "project_baseline": "1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc",
        "independent_probe": {"original_path": INDEPENDENT_PROBE.as_posix(), "sha256": hashlib.sha256(probe).hexdigest()},
        "test_counts": counts, "commands": commands,
        "status": "awaiting_review", "no_new_network_requests": True,
        "initial_manifest_refers_to_commit": REPAIR_BASELINE,
        "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
    }
    receipt_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"code_sha": CODE_SHA, "code_tree": tree, "created_at": ended, "test_counts": counts}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
