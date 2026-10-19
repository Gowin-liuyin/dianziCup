"""Write the independent first-review result from actual command receipts."""
from __future__ import annotations
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN=Path(__file__).resolve().parent
REPORT=Path('D:/dianzi/reports/reviews/recovery/G-E-R18-public-models-review-1.md')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
rows=[]
for name in ('new_models','old_sdk','old_schema','independent','complete_support','style','format','typing'):
    record=json.loads((RUN/(name+'.json')).read_bytes())
    counts=record.get('junit_counts')
    total=(f"{counts['passed']}/{counts['failures']}/{counts['errors']}/{counts['skipped']}" if counts else '非测试检查')
    command=subprocess.list2cmdline(record['command'])
    rows.append(f"| {name} | `{command}` | {record['started_at']} / {record['ended_at']} | {record['exit_code']} | {total} | [raw](../../runs/recovery_r18_public_models_review1_20261016/{name}.log) / [receipt](../../runs/recovery_r18_public_models_review1_20261016/{name}.json) |")
table='\n'.join(rows)
content=f'''# R18 public extension typed models · 首次独立审查

文档首次创建、写作开始/结束时间：{now} / {now} / {now}。证据截止：{now}。
Reviewer：/root/r18_public_models_first_independent_review；本轮为新非作者首次 review。任务/审查状态：**needs_changes**；不是 accepted。

What this change does：本切片新增冻结公开扩展 schema 的十个 SDK DTO 及根导出，并检查任务状态、风险引用、组件索引和来源 fixture/live 标记。现有八对象、十四个旧定义、原客户端/CLI/MCP 代码与旧测试保持。它只提供 typed payload 校验，不能证明 PostgreSQL 引文支持、对象归属、ACL 或在线来源能力。

## 1. 固定范围、输入与权限

- 已审源码：`be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958`；固定 detached review WT：`D:/wt/r18pm-r1`，不是作者 running 目录。
- 完整变更基线：`1315194a8ee421b7f1131a901221f31f4cacb536`。`2bb2e122644bd2e2084056ca0251bcd85583c664` 是先前十 DTO 源码；be4 只在 SourcePage 增两行约束与直属三个 case，不能把 2bb 当十 DTO 变更前的 root 基线。
- 作者初材料：`a45ae4d9f34ef8217c186bda9260d63cae6c555d`；最终材料：`08fb9623f4cdda0facd1314ab8174376a6504798`，均按 `git show <commit>:<path>` 读取。
- 最终 `payload_manifest_mode_fix.json` SHA256：`8e9b5b105dc9a872769ee157d5be6fa001d16a63251516ebcb7a06f114f32a97`；作者报告 SHA256：`e4af5bdc5efdb9085cf1fb0442f7658a0af81255b8ea9d948cad04c3bc8e60e5`。129 payload 的 raw SHA256、Git blob 与长度全部一致。52 source input blob 一致，49 非拥有依赖与 root 基线一致；唯一 checkout raw 与作者 raw 不同的是新增测试文件，字节差异仅 LF/CRLF，Git blob 相同，未修改被审 tracked 文件。见 [verified_inputs.json](../../runs/recovery_r18_public_models_review1_20261016/verified_inputs.json)。
- 补充 CR 固定 `d8847a8026e2c38272ca9e1a67419d5d5941d763:docs/decisions/CR-R18_public_read_identity_bindings.md`；SHA256 `d7b5b64533c64b919c0c745c16bded4e7bd42f7e5b859dd4aef5b4b14d747b96`。与派发时 Root raw snapshot 字节完全相同，两个版本均留在 ownrun。Root 明确说明 complete 也不允许摘要 unknown/conflict；supported 每 index 必須有本次分级 finding，即使低于阈值；排除必须 assessment_id 与非空完整 citations。此解释落实原 CR“无分级/缺证据不能 complete/none_confirmed”，没有修改 schema/阈值/分母。

已亲读 AGENTS、00执行图、R18恢复卡、T04/T32/T35、03/04/05/06合同、CR-R04/09、两份 CR-R18_public*、原 v2 与扩展 schema、作者冻结新测试、全部 models.py、根 exports、client/CLI/MCP/stdio 消费者及最新 Ponytail 5.3 review。Root 有大量进行中修改，未暂存、覆盖或使用它们作代码证明。

唯一作者业务变更：`sdk/python/ai_intel_client/models.py`、`__init__.py`、新增 `sdk/python/tests/test_public_extension_models.py`。Reviewer 仅写自己的 review/ownrun；没有修改业务/schema/旧测试/progress、push、accepted、读取秘密或 holdout，也未 spawn。

## 2. Must fix

1. **complete/none_confirmed 资格检查仍允许未知或缺必要证据**（`sdk/python/ai_intel_client/models.py:399`、`:401`、`:416`、`:437`；任务联合解析入口 `:554`、`:571`）。
   - **职责与触发：**RiskSummary 检查阈值 finding 与 confirmation；StackCheckEnvelope 应按本次返回 scope 保留分级与排除证据。输入一条 current 排除结果和空 findings，把摘要设为 `coverage=complete, confirmation=unknown/conflict`；或者 current supported 但无任何 grade finding、排除缺 citations/assessment_id，设 `complete/none_confirmed`；或 partial 的 unknown/缺 grade 仍设 none_confirmed。
   - **实际结果：**以上 payload 都满足原 JSON schema，并被新导出的 DTO 接受、序列化。前两种还被 `succeeded TaskResultEnvelope` 的 `TypeAdapter` 联合调用方接受。独立 9 个应拒绝负例全部 `DID NOT RAISE ValidationError`，不是环境错误；输入和输出见 [observations.json](../../runs/recovery_r18_public_models_review1_20261016/observations.json)，失败原文见 [independent.log](../../runs/recovery_r18_public_models_review1_20261016/independent.log) 与 [complete_support.log](../../runs/recovery_r18_public_models_review1_20261016/complete_support.log)。
   - **影响：**公开 typed 模型会把未解决风险、无分级或缺排除证据的结果认可为范围完成/未确认风险，违反冻结风险合同。当前固定旧 CLI 仍返回 legacy=2，不能从这个缺陷推断它已输出错误 CLI=0；新增 SDK/MCP/producer 接线后会继承该不可信 payload，故本 typedmodels 切片不能 Ship。
   - **最小修复与复测：**在现有 RiskSummary validator 拒绝 complete 与 unknown/conflict 摘要、以及 none_confirmed 携带未知/冲突/过期资格；在现有 Envelope validator 检查 complete/none_confirmed 的每个 supported index 至少关联一条本次有效分级 RiskFinding（等级可以低于 minimum），排除结果需有效 assessment_id 和非空完整 citations。沿用已有引用与范围校验，不新建服务、不改 schema/金标/旧 oracle，也不把 partial 的 evaluated_components 机械强制为原请求总数。真实 claim/event 归属、支持内容及 ACL 仍由 producer 的 PG 最终检查承担。修后在新固定 WT 复测下面 9 个负例、保留本次红日志，跑新增/旧相关回归；新 client/MCP 综合候选另审。

## 3. 已证与调用链

- 十个模型每个公开字段、required、extra=forbid 和正例 wire roundtrip 与 frozen schema 相容；独立 schema oracle 对字段类型、枚举、长度、数值/数组上限、缺 required 与隐藏额外字段作负例交叉检查。UUID/RFC3339、任务 owner/poll_uri、九 job 状态、task_type/result、终态错误与步骤列表由新126覆盖，个人新增错 owner case也通过。
- 原十四 defs 逐项结构相等；models.py 的旧完整正文是新正文精确前缀；原七个根导出全部保留，新十导出可按 public package 构造解析。所有旧 SDK 消费者/测试/fixture 与基线 Git blob 一致。
- CVSS 五分带/四版本、严格 bool/int 处理、finite 分数、阈值、finding 重复与同 assessment/claim 的 payload 绑定冲突均有新126证据。finding 必须同 index/same assessment/current/supported/citations。独立正例证明 medium 6.0 低于 high 阈值仍保留分级并允许当前 none_confirmed；修复不能把它要求成高危。
- `evaluated_components` 是已执行数量，unknown 仍计数；Envelope 检查 <=len(results)、索引在返回范围。独立正例验证 partial 的 unknown 已评估可计1，返回2个结果仍允许实际执行数1。完整原 request 分母由 check_stack caller/producer 持有，不由这个 DTO 猜测。
- SourcePage 双向 live/fixture 混合拒绝；空页保留明确模式，enabled 不等于 healthy。真实 PG 观测仍未运行。
- 独立 CBM 0.11.0 在仅7个 SDK Python 源文件上新建索引 `dianzi-r18pm-review1-20261016`：180 nodes/697 edges，not_indexed/skipped/partial/unusable均0。cache `/tmp/dianzi-r18pm-review1-cbm-20261016` 在工作区外；index/architecture/schema/outline/trace 均实际运行，raw与完整参数保留 ownrun。`DianziClient.ask` outbound trace 到 `_ask_result`/`_post`/`ask_async`；RiskSummary validator 的静态 callers=0是 Pydantic 动态调用局限，未把它认作不可达，实际 public caller负例补足。
- [rg_consumers.log](../../runs/recovery_r18_public_models_review1_20261016/rg_consumers.log) 与源码核对 client `_ask_result/_stack_result`、CLI legacy返回2、MCP `_complete_result/wire_json` 和 stdio入口。当前 source 的 client/MCP 仍仅原两业务操作，新增模型消费者是根导出与TaskResultEnvelope的内部联合；并行六工具尚未合入这个被审 source，未拿未冻结运行目录代替综合审查。

## 4. 真实命令与结果

以下 workdir 全为 `D:/wt/r18pm-r1`，input source全为 be4b9114完整SHA；数据全部显式 synthetic fixture，外网/产品PG/真实模型/费用调用0。pytest `--no-cov` 只作隔离 SDK/JSON检查，未改全仓60%覆盖门，也不声称全仓覆盖通过。passed/failed/error/skip 列按 JUnit 解析，非测试检查不凑测试数。

| 检查 | 完整实际命令 | Asia/Shanghai开始 / 结束 | exit | passed/failed/error/skip | 原始证据 |
|---|---|---|---|---|---|
{table}

指定去重集：126+349+23=**498 passed /0failed/0error/0skip**；作者历史122/123或重复349不累加。独立集38+5=**43 cases，34 passed /9failed/0error/0skip**；两集合全加541 cases，只是有限合同检查数量，不是产品准确率。

旧349只跑一次，50.341894秒，timeout上限300秒；5个原 record_property/xunit2 warnings 保留。Windows旧 TCP finally 10053 此次未复现，未重跑挑绿或修改旧清理 oracle；不能据此宣布原宿主风险消失。所有原 stdio/native/loopback observations保存到 [old_sdk_native_evidence](../../runs/recovery_r18_public_models_review1_20261016/old_sdk_native_evidence/)。旧 cancellation_observation 本身报告 executing_cancel_underlying_io_stopped=false，是继承旧场景的限制证据，未改成true，也不为本DTO签真实取消能力。

`independent_stdio_resources.json` 记录5请求/peak4/queued_dispatches0/shutdown_all_eof=true。最终精确检查本轮测试父PID及本review固定fixture/native evidence命令路径，现存父进程0、归属子进程0，无需终止他人PID；见 [own_process_cleanup.log](../../runs/recovery_r18_public_models_review1_20261016/own_process_cleanup.log) 与 observations。没有对外部服务或其他 Agent 进程清理。

读取、freeze核对和 CBM 命令不是业务测试数：所有CBM/capture收据保存实际cwd/start/end/exit/full argv。材料核对21:28:46.451011–21:29:18.715864 exit0；固定CR和输出观察21:30:51.804695–21:30:52.791899 exit0。初输入验证把author raw与新checkout raw机械相等，因新增test LF/CRLF在assert退出1（时间未单独保留，工具原输出保留）；随后保留raw差异并按源Git blob核对，没有转换source或放宽业务判断。初最终观察 helper 缺psutil真实退出1（未执行清理、没有业务case），改用原生PowerShell精确归属查询后exit0；没有安装新依赖。初路径定位出现不存在 sdk/python/pyproject.toml、docs/contracts、tools/plugins，属于定位错误，不记skip/能力通过。

## 5. 未通过、未运行与验收范围

本切片 unit/contract=**failed**（9个独立确定业务红）；指定兼容回归/静态检查passed。真实 PG producer、claim/event支持与归属、当前ACL/epoch/paging、安全身份撤销、默认公开API、六MCP工具综合调用、Streamable HTTP产品认证、真实模型/来源、三类plugin沙箱、打包/安装、真实Codex/Claude兼容、frontend/e2e/live/manual均**not_run**。没有fixture冒充online；外部live最终验收仍不具备本轮证据。

E1/T04证据只限新增DTO兼容与有限负例；F2/F3风险/unknown不变量发现上述缺陷。T32/T35/T51、整R18、G-E、六producer/MCP和三插件不扩签，PG权威事实/官方分数/原盲测/指标分母没有修改。

Reviewer改动文件只为本报告与 `reports/runs/recovery_r18_public_models_review1_20261016/` 的自有脚本、合成case、日志/XML、输入snapshot和manifest。临时pytest/mypy/cache目录不作为提交材料；scoped `.gitattributes` 仅用于该review ownrun raw证据，不能影响产品源码或旧测试。

Verdict: **needs_changes，先修1**。下一任务建议：作者只修现有资格validators及直属必要负例，冻结新source/material；原reviewer在新WT对同根因修复复核，再交综合client/MCP/producer审查。主控可以登记这个独立意见，不能把原498绿直接登记本切片 accepted。
'''
REPORT.parent.mkdir(parents=True,exist_ok=True)
REPORT.write_text(content,encoding='utf-8',newline='\n')
print(json.dumps({'report':str(REPORT),'written_at':now,'state':'needs_changes'}))
