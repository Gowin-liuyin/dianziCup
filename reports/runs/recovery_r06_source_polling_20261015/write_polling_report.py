"""Archive self-check facts for the immutable polling code without signing acceptance."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

run = Path(__file__).resolve().parent
root = run.parents[2]
at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
code = "93c458a0f97b65198d1fb690d42634b77342bb3c"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == code
commands = [json.loads((run / ("polling_" + mode + "_frozen.json")).read_text()) for mode in ("pure", "pg", "ruff", "mypy")]
assert all(item["exit_code"] == 0 and item["head"] == code for item in commands)
table = "\n".join(f"| {item['argv'][3]} | {item['started_at']} / {item['ended_at']} | {item['exit_code']} |" for item in commands)
report = root / "reports/tasks/R06-source-polling.md"
assert not report.exists()
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(f"""# R06 · 固定公开来源自动轮询

文档首次创建/本次写作开始/结束/最后更新时间：{at}
任务切片awaiting_review、implementation complete；整R06/G-C in_progress/partial。作者/root；分支codex/r06-source-polling；基线52433474f66a900c56ee6d5478337b0ec83d6eda；代码冻结{code}，独立r06_periodic_collection_independent_review正在审此SHA，不自签accepted、未push。代码编写实际起止未单独记录，不拿文件mtime代替；测试时段如下。

## 行为与范围

可信SOURCE_POLLING_ENABLED默认false、compose显式透传。开启后beat60秒→poll_due→单个PG事务→九固定来源live root jobs/outbox→既有dispatcher/worker。vLLM30分钟，余60分钟，每轮最多5页；参数不来自网页/任意URL/租户。关闭配置后任务直接返回disabled且不连PG，已排队任务/原文/历史保留。

仅新增source_polling.py，复用既有SourcePageRequest/enqueue_source_page、来源注册、source_cursor和job_runs/payload/outbox；没有新增调度表、迁移、依赖或内存业务真相。UTC桶固定window_end/key；重复tick/多进程/重启不增加同桶root jobs；包含continuation的该源active工作先续接，>500active或非法/超4096byte source payload明确报错不继续放大队列。全球公开source管理员权限先于DB访问检查，普通租户不能调用。调度事务回滚无半成品，实际外网IO仍只由已有worker网关执行。

变更8文件494行：source_polling.py141、settings1、runtime33、compose1、直接unit84/PG206、CR-R06_periodic_collection与source_polling运行手册；测试为重启/并发/回滚/队列与停用必需，未建通用调度框架。合同只落实已批准R06:T49/T54持续采集，不改变官方门槛、金标、分母或原T整卡条件。

## 实际验证

命令cwd D:/wt/r06-source-polling/backend；完整argv/精确秒级起止/exit见各frozen.json。pure原60覆盖门保持；PG显式test_dianzi_r06_catalog_polling_20261015和独立UUID schema，未运行降级或硬编码开发库。当前作者未单独保存public前后snapshot，独立review要求补核对；不以fixture模式计来源live。

| 项 | 开始 / 结束（+08） | exit |
|---|---|---|
{table}

冻结pure1777passed/10real_pg deselected/0fail/0skip，覆盖74.15%；PG10passed/0skip（真实PG、显式fixture source），含3并发、实际另进程restart、事务回滚、501active上限、非法/超大payload、旧OSV worker实际PG执行。Ruff、mypy93通过；格式检查前使用既有Ruff formatter，产品diff没有范围外文件。unit focused19passed包含旧worker2；原17?计数以raw19为准，不相加为整卡分母。最早测试ModuleNotFoundError exit2保留polling_initial_red；首轮lint格式/长行错误为作者工具输出，未单独保存完整lint初始日志，最终check0可复验。environment_sync实际退出码未单独封存，uv日志与成功运行自己的venv保留，不编造exit0。

CBM官方0.11索引src-only，基线524图1233nodes/6137edges，冻结93图与schema/trace原输出在cbm_*_frozen.log；缓存/tmp/dianzi-cbm-r06-source-polling-20261015在仓外。图确认runtime.poll_due_public_sources→enqueue_due_source_collections→原source enqueue/outbox；另rg查配置/入口/全部callers。没有edge不当无调用，实际beat注册由unit、PG由integration交叉核查；未启动真实broker/beat/source，live/frontend/e2e/manual未运行。

## 限制与问题

采集间隔只是策略，不证明≤6小时/漏采率；限额与失败仍由真实日志判定。固定source目录不是九个官方类别或九条业务通道；CNNVD/自有webhook/EPSS/KEV另补，不被此poller替代。当前新7源依赖另审两Must：CAC最后条文缺失仍full_text，OSV非法或超精度时间被当精确UTC；主控在独立source-boundaries-fix修复，未关闭前不做九源live或跨阶段验收。本切片自检不能背书那些解析语义，资料读取UI的先前独立Ship也不能背书自动采集。

下一步全新reviewer核对93与本材料→修复/定向复核→与source边界修复和独立Ship来源管理UI合入→实际有界beat/worker/API/浏览器九源验证。整阶段另需新reviewer。没有新费用，模型/测绘调用0。独立结论、合并后regression与真实持续观察仍待取得。
""", encoding="utf-8")
files = [p for p in run.rglob("*") if p.is_file() and p.name != "artifact_manifest.json"]
(run / "artifact_manifest.json").write_text(json.dumps({"recorded_at": at, "code_sha": code, "files": [{"path": str(p.relative_to(root)).replace("\\", "/"), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"report": str(report), "artifacts": len(files), "code_sha": code}))
