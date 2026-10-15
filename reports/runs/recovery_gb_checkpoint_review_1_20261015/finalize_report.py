from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

RUN = Path(__file__).parent
REPORT = RUN.parents[1] / 'reviews/recovery/G-B-checkpoint-review-1.md'
started = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
report = REPORT.read_text(encoding='utf-8')
(RUN / 'report_prior_final.md').write_bytes(REPORT.read_bytes())
report = report.replace('此时审查尚未结束，最终截止时刻以末尾封存记录为准。','最终截止时刻以末尾封存记录为准。')
old = '**阶段状态：needs_changes，尚不能 Ship。** 1ff 的 clean checkout 安全回归失败已在 8c 的独立全套复跑中关闭；进一步真实 PG 探针发现来源写接口的三条幂等合同反例。另有 frozen 环境公共 schema 格式校验依赖缺口。主控正在修复；本报告不以其自检替代新 SHA 的独立复验。最终意见将在末节明确追加。'
new = '**最终阶段意见：Ship，限定冻结 SHA `1927eeb00a7e0c1335f76340b0382f46102f08f2` 的 R04/R05 阶段切片。** 本 reviewer 在第三个全新 detached WT 独立复跑后，初审 clean checkout 字节、来源 HTTP 幂等与 frozen schema 格式三项 Must 全部关闭；保留全部旧红例。RFC850 完整50年边界仍为明确非阻断债务。此意见不登记 accepted，不签后段整卡或正式质量/性能。'
assert old in report
report = report.replace(old,new)
report = report.replace('### Must fix','### 初审 Must，最终已逐项复验关闭')
report = report.replace('`ingestion/source_jobs.py` 原 L248–253','`ingestion/source_jobs.py` L238–240')
report = report.replace('两个R02 probe的精确历史raw source SHA仍须补保存或明确缺口，不能拿规范化blob掩盖该缺口。','两个R02 probe的混合行尾原始字节已在1927按精确path保留；最终历史source SHA 51/51、可核对Git source标识39/39，新增15的来源字面量全部在指定行匹配。旧G-A记录的可选source_content_git_blob与历史review_ref缺口没有冒充新记录完整性；详见逐条origin_metadata。')
report = report.replace('未把第三方55命中分类为fixture','原 metadata 70命中/58文件、第三方55命中/47文件均独立重算；未把第三方55命中分类为fixture')
begin = report.index('| label / 命令范围')
end = report.index('\n数据库：',begin)
report = report[:begin] + (RUN / 'historical_commands.md').read_text(encoding='utf-8') + '\n' + report[end:]
report = report.replace('审查仪器错误另列：','审查仪器错误另列（均保留原日志，不改为skip）：')
report = report.replace('source-origin审查先误把 git hash-object过滤后的SHA1当raw SHA1，已按原提案代码解释，不能把该仪器误判当业务错误。','source-origin审查先误把 git hash-object过滤后的SHA1当raw SHA1，已按原提案代码解释，不能把该仪器误判当业务错误。最终自制role撤权探针首轮错误地把tenant=None的global admin仅改成viewer，违反既有users CHECK，实际3pass/1fail(503)；修正为合法viewer+tenant后，原4项加GET3项共7pass。汇总脚本首次误读browser_initial.json文件名，exit1，随后读取实际browser.json；这些均非产品defect。')
report = report.replace('下一步只复核主控固定修复候选的来源幂等/事务锁、frozen格式依赖和精确source档案。新代码应重新完整unit/contract/security、受影响PG与必要frontend检查，再据同SHA证据给阶段意见；原失败和非阻断RFC850保持。不更新progress、不push、不替实现者登记accepted。','下一步由主控依据此有限阶段意见登记相应阶段/CR与切片，再按其授权进入后续批次；本reviewer不更新progress、不push、不替实现者登记accepted。原失败与非阻断RFC850保持。')
report = report.replace('**Verdict（本中间证据截止）：fix 1 and 2 first；3已在8c关闭，4为明确非阻断债务。Not checked：上述正式评测/人工/容器/后段范围。**','**历史中间意见：1ff/8c阶段 needs_changes；来源幂等与frozen格式修复前不允许阶段Ship。原三项Must及各红例不删除，最终复验见下节。**')
report += '''

## 8. 最终冻结候选的独立复验与阶段意见

第三 detached WT `D:/wt/gb-stage-final` 创建前确认路径未占用，实际 HEAD=`1927eeb00a7e0c1335f76340b0382f46102f08f2`，完整tree=`9c58236461186803ece26d1dda70186094199ea0`；backend/src=`2e85b41a18456d462619959e22622a23e4ca7b78`，frontend/src=`5862a0f0a690bf66f3f3ea7f3fdbd2caa9b62e8a`。后端相对8c只有source_routes产品代码改变，前端产品和整个src tree相对8c均未变；相对dc014不能称整个业务tree相等。问答/检索/worker/原文writer与真实dc014代码逐blob相同，来源HTTP鉴权/幂等新行为由本次真实PG测试覆盖，没有新付费产品调用。

本WT使用全新 `uv sync --frozen --project backend --extra semantic` 和 `npm ci`，不是沿旧env补pip。原jsonschema schema/负例不变，官方 `format-nongpl` extra安装后原56项通过。full backend **1419pass/0fail/0error/0skip，10 real_pg deselected**，coverage原始5196/7049=`73.71258334515534%`，原60门未改。10真实PG安全用例在49项source/security套件另行实际执行，未改skip。Ruff check、190文件format、mypy82源码通过。

最终真实隔离PG：49来源任务/权限/执行器/合同、25原文、41知识API、35向量与问答、8问答进程/并发/锁序、删除支持证据1、原3来源幂等、7新增POST/GET auth锁、11正式来源HTTP，共各套件全部pass/0fail/error/skip，不加成题目或性能分母。后两源套件继续本人数据库bba59f55；最终49来源/security另建 `test_dianzi_gb_stage_review_20261015_a15dd559`，精确RUN_ID、UUIDschema与原guard均有效。新增正式11测试直接导入原函数，单换本人空库资源fixture，原业务断言不改。

来源Must1的原无键四POST现在422且0PG行，两个独立管理员与两个source_kind同键各产生独立job；两前缀同主体/来源重放与并发只一个job，异body409。来源源码L128–141、L153–179和L204复用原auth session/users share锁，在同PG提交/读取事务验证当前身份。亲测锁前logout→401、合法降权/迁租→403并0job；持锁logout在PG阻塞，提交后才撤销；GET锁前撤销/降权/迁租均拒绝且无job正文。旧裸key任务保留、无法可靠补actor归属；已读CR-R04-R04_source_commit的停未知重投/核对job_id迁移限制，不声称旧键可无损推断迁移。

最终frontend type/lint/build、**254 unit pass**、**17 fixture browser pass**均在1927自己的node_modules/src执行。浏览器包括1366/390、reduced-motion、键盘引文、固定revision、未知写入body/key保持、权限/异常状态、HTML按文本及来源任务状态；没有产品API或模型POST。raw manifest三候选全文SHA256均`b525699f38bf2deb2eac85ef1912e71ae8049503f903eb07740438729e651240`，51/51 WT raw/HEAD blob/span/值、0拒绝，scanner与ignore diff为空。历史source_sha51/51，Git标识39/39；两个R02原始mixed-CRLF字节缺口关闭。

最终CBM重新索引本人backend/src：1085nodes/5219edges，not_indexed/skipped/partial/unusable0；重新get_graph_schema与trace_path build_source_router/lock_authenticated_scope。router trace确实连接create_application与POST/GET route。嵌套lock_source_scope未索引的失败原样保留，用rg、源码L128/L159/L204与7真实PG探针补证，不冒称静态图完整。

root实际secret staged scan是核对其元数据：9refs/321patterns/32本次staged路径、0命中；本reviewer没有取得秘密值，实际秘密精确扫描仍明确not_run_by_reviewer。2370/45504351 raw完整性为核对既有主控receipt和属性机制，不声称本reviewer重新生成2370原始历史字节。两份venv before/after entries完整清单相等、4857/6532与inventory SHA对应原receipt；未删除原失败或豁免第三方文件。

'''
report += (RUN / 'final_commands.md').read_text(encoding='utf-8')
report += '''

完整命令收据及所有仪器失败包含在 `reports/runs/recovery_gb_checkpoint_review_1_20261015/command_summary.json`；逐文件依据SHA在document_inventory.json，最终版本/hash/coverage核验在final_metadata.json，亲测live溯源在live_provenance.json。JUnit计数与browser JSON可以独立重算；所有套件有实际起止秒级+08，不拼不同候选的结果声称同版全绿。

**最终 Verdict：Ship — 仅1927固定R04/R05阶段与当前映射切片；Must1/2/3已独立关闭。Should4 RFC850债务开放；Not checked 为第7节的正式评测/人工/容器/后段范围。** 此限定意见已覆盖本阶段六项验证和历史实际live链路溯源；新来源HTTP行为由真实PG认证/事务测试证明。没有新模型live、没有质量金标、当前10212.6966ms真实完整响应不满足≤5s，不称生产可用，不修改阶段状态。
'''
ended = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
report += f'\n最终报告写作实际起止：{started} → {ended}；证据截止为最后已结束command receipt，封存时刻{ended}。审核停止于本G-B阶段。\n'
REPORT.write_text(report,encoding='utf-8')
(RUN / 'report_write_receipt.json').write_text(json.dumps({'started_at':started,'ended_at':ended,'path':str(REPORT),'sha':'1927eeb00a7e0c1335f76340b0382f46102f08f2','verdict':'Ship limited R04/R05 stage slices','accepted_or_shared_state_written':False},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'report':str(REPORT),'bytes':REPORT.stat().st_size,'started_at':started,'ended_at':ended}))
