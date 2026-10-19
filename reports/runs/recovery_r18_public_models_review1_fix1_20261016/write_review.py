"""Write a bounded fixed-source recheck from retained independent receipts."""
from __future__ import annotations
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN=Path(__file__).resolve().parent
REPORT=Path('D:/dianzi/reports/reviews/recovery/G-E-R18-public-models-review-1-recheck.md')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
rows=[]
for name in ('independent','complete_support','eligibility','new_models','old_schema','old_sdk','style','format','typing'):
    record=json.loads((RUN/(name+'.json')).read_bytes())
    counts=record.get('junit_counts')
    summary=(f"{counts['passed']}/{counts['failures']}/{counts['errors']}/{counts['skipped']}" if counts else '非测试检查')
    rows.append(f"| {name} | `{subprocess.list2cmdline(record['command'])}` | {record['started_at']} / {record['ended_at']} | {record['exit_code']} | {summary} | [raw](../../runs/recovery_r18_public_models_review1_fix1_20261016/{name}.log) / [receipt](../../runs/recovery_r18_public_models_review1_fix1_20261016/{name}.json) |")
table='\n'.join(rows)
text=f'''# R18 typedmodels fix1 · 原非作者定向复核

文档首次创建、写作开始/结束及证据截止：{now}。Reviewer：/root/r18_public_models_first_independent_review。
结论：**Ship，仅限公开模型风险资格修复**。任务保持由主控登记，本报告不写 accepted，不签整R18、G-E、六producer/MCP、默认API或三plugin。

What this change does：在现有 RiskSummary/StackCheckEnvelope 的 after validators 增加13行、替换2行，使 complete/none_confirmed 只能来自本范围完整分级或有引用的排除。未知/冲突摘要、缺分级、缺排除引用/ID 被拒绝；明确 partial 的合法小计数与低于阈值的分级继续保留。

## 1. 冻结对象与证据

- 新独立短WT：`D:/wt/r18pm-r1f1`，执行期detached固定 source `011ea225d18b7511a19d7d6056288f799bb83f20`；未读取作者 running 目录。
- 前源码 `be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958`、基材料 `08fb9623f4cdda0facd1314ab8174376a6504798`、新作者材料 `1474b1f9af37ed59cfe79ed83f5864514d45d3ec`。
- models Gitblob `32b48ca953f867d4d7819de94c352d7173312489`；__init__仍 `80a4c46b7374c10ba5d6eea10afc462360712e74`。只改models和新增fix1直属26case；原126、旧349、43独立probe、原schema和caller source没有修改。
- 作者178payload raw SHA256、size、Gitblob逐项全一致；manifest SHA256 `e1afbb27ee2481433442d12d207770d1895803ccb218135d6527601a8c83cb57`；作者fix1报告SHA256 `b7573d632ed3a21bb215395027c573bc0d01eb1bce8243d7918b7093dcba2e52`。54input sourceblob全部符合，52nonowned与基线一致；新fix1测试checkout raw与作者raw仅LF/CRLF不同，Gitblob和内容一致。见 [verified_inputs.json](../../runs/recovery_r18_public_models_review1_fix1_20261016/verified_inputs.json)。
- 两原独立probe从首次封存 `a7bee69be46d3b9ecc611f188723a81cb2569dd2` 按 Git原bytes复制，SHA256仍 `36f92cdaf3faab7a500befd29b878cee3aba320242ded236d421f19364c40384` 与 `74bb7251e00f652b055815d336321b4948a578f95488703e35366b149fb75de8`，并与作者材料中所复制probe逐字节相等。原hardcoded ROOT只读schema；该冻结schema与新WT原bytes相同；实际 DTO import 来自新WT的models.py，observations记录了绝对路径。
- 首次 [needs_changes报告](G-E-R18-public-models-review-1.md)、43中的9红和原rawmanifest不覆盖；本次另建ownrun/report。沿用已亲读AGENTS、执行图、R18/T04/T32/T35合同、03–06、CR-R04/09与两CR-R18_public，以及 `d8847a8026e2c38272ca9e1a67419d5d5941d763` 的读取身份/组件语义。无需改公共schema、阈值、金标、分母或partial等号。

## 2. 原 Must fix 1：关闭

亲读固定代码 `models.py:401`、`:403`、`:437`、`:446`、`:453`：complete不能unknown/conflict；none_confirmed须complete，继承current和无unknown-index保护。Envelope完整范围每行要assessment_id与非空citations；supported每index另需有效RiskFinding，沿用same/current/supported绑定。排除不强加CVSSgrade，medium/score0分级也不能因低于minimum被删除。

原43原样复跑38+5全部通过；原9 DID NOT RAISE在本源码全部转为正确拒绝，包括public导出Envelope与succeeded TaskResultEnvelope/TypeAdapter联合路径。直接观察保存九个输入/拒绝结果，见 [observations.json](../../runs/recovery_r18_public_models_review1_fix1_20261016/observations.json)。没有改原期望或测试为skip。

合法partial已执行unknown仍计1、返回2行可保留较小evaluated_components；没有机械要求partial等于原request或把缺分级集合强行塞成所有unknown indices。独立原正例仍通过。新26还核对TaskResult succeeded/partial、合法complete低grade/排除、score0、保留confirmed同时显示unknown，以及旧CLI实际helper保持exit2。整个旧349原协议消费者复跑一次通过；旧client/MCP仍消费原StackCheckResult，未把新6工具未冻结调用方当已接线。

Schema只提供字段层校验，qualification由typed validator补足；无schema漂移。原十四defs相等、旧models完整正文精确前缀、旧exports/source/oracles均保留。真实PG claim/event归属、引文支持、当前ACL/epoch和原request完整分母仍由producer验证，本次不以DTO证明这些内容。

## 3. 保留的 Should fix 2：原 Windows fixture cleanup

**归属旧fixture，非本次models修复的新问题**（`sdk/python/tests/test_independent_native.py:142`、`:144`，`TcpEvidence.handle`）。作者最终501运行500passed/1failed，body清理路径在 `await writer.wait_closed()` 抛WinError10053，跳过writers/tasks.discard，随后fixture退出assert失败；raw traceback保存在 [sdk_all_final.log](../../runs/recovery_r18_public_models_review1_fix1_20261016/frozen_author_inputs/sdk_all_final.log)。

这条旧测试消费AskRequest/旧SDK IO，不使用新增RiskSummary/Envelope；fixture与caller Gitblob与修前完全一致。作者最初全套绿、最后全套红和body定向1绿均保留，定向绿不能改写全套红。本独审旧349只跑一次53.273833秒/349pass，10053本次未复现，未重复挑绿、改旧测试或混入其他Agent的新helper代码。

最小独立修复应确保该fixture finally路径即使发生已证连接终止错误也必清除其本地集合，并按预期错误记录，不吞业务断言、不加长deadline、不改peer EOF oracle或skip。Root已另派唯一作者负责helper；其新source需要另审，不能借本报告给它背书。若暂留，该宿主仍可能出现fixture清理红。该已知Should不阻断**本模型切片**的同根因资格修复，不表示完整SDK历史失败已消失。

## 4. 实际验证与命令

以下cwd全部 `D:/wt/r18pm-r1f1`，input source全部011ea225完整SHA；synthetic fixture，0外网/产品PG/真实模型/实际秘密/holdout/收费。pytest `--no-cov`只隔离SDK/JSON，未改全仓60%覆盖门，也不声称全仓coverage通过。

| 检查 | 完整实际命令 | Asia/Shanghai开始 / 结束 | exit | passed/failed/error/skip | 证据 |
|---|---|---|---|---|---|
{table}

独立去重总数43+26+126+23+349=**567 passed /0failed/0error/0skip**。旧349只一次 bounded batch，timeout上限300秒；5原record_property/xunit2 warnings保留。作者最终同逻辑源码的567集合566pass/1旧fixturefail属于作者历史真实结果，不改成绿。非pytest观察、CBM、材料核对、定向重复1例不新增分母。

本次unit/contract=passed（模型有限切片）；独立旧SDK兼容回归=passed（此次运行）；作者旧fixture历史失败保留。产品PG/integration/security整体、defaultAPI、六工具综合、StreamableHTTP认证、插件、安装包、actual Codex/Claude、frontend/e2e/live/manual=not_run。E1/T04的兼容与F2/F3资格不变量只引用本行证据，不计为性能、准确率或来源在线能力。

## 5. 调用链、独立工具与清理

独立CBM SDK source索引 `dianzi-r18pm-review1-fix1-011ea225-20261016`，7Python files/180nodes/697edges，未索引/跳过/partial/unusable均0。cache `/tmp/dianzi-r18pm-review1-fix1-cbm-20261016` 在工作区外。index/architecture/schema/models-outline/trace均有完整argv/cwd/start/end/exit/raw；models-outline确认RiskSummary351–409、Envelope412–454、TaskResult565–598，匹配011源码行号。静态Pydantic callback caller0不作不可达推断，原43+26实际动态解析补证；rg全SDK/后端/相关schema消费者与亲读client/CLI/MCP交叉核对。

第一次复制capture helper漏替换WSL `/mnt/d/...` 路径，虽然exit0却索引了旧WT；[cbm_index_old_source.json](../../runs/recovery_r18_public_models_review1_fix1_20261016/cbm_index_old_source.json)/log保留，不能归为011证明。纠正路径并用新project重新索引后才作上面的结论。没有改业务或用作者索引替代独立索引。

材料核对实际21:50:12.950196–21:50:46.304798 exit0；固定caller/cleanup观察21:51:31.735146–21:51:35.219794 exit0。精确查询本轮测试父PID和本WT fixtures/native evidence命令路径：现存父进程0、归属fixture进程0、父PID TCP socket0，未终止他人进程。原native观察5held请求/peak4/queued dispatch0/shutdown_all_eof=true，原stderr/stdout/TCP observations在ownrun。它们只是synthetic loopback/stdio，不冒充产品live。

Reviewer只新增本报告和 `reports/runs/recovery_r18_public_models_review1_fix1_20261016/` 自有probe副本、run脚本、日志/XML、raw输入和manifest；没有源码/schema/旧tests/state/accepted/push、秘密/holdout读取或spawn。scoped `.gitattributes`仅本ownrun raw保留；pytest/mypy/__pycache__生成cache不封入材料。

Verdict: **Ship，原Must1关闭；Should2归属旧fixture仍保留。**下一步由主控根据独审登记模型切片，再让六工具综合候选拉确切modelsblob32b48ca9并作自己固定版本审查；producer须真实PG验证支持/ACL/原request分母。整R18与原T最终验收继续partial，不扩签。
'''
REPORT.parent.mkdir(parents=True,exist_ok=True)
REPORT.write_text(text,encoding='utf-8',newline='\n')
print(json.dumps({'report':str(REPORT),'written_at':now,'verdict':'Ship limited model qualification fix'}))
