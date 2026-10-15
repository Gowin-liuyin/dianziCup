"""Record fixed-95ba API recheck results without accepting unrelated pipeline work."""

import hashlib
import json
import subprocess
from datetime import datetime,timedelta,timezone
from pathlib import Path

run = Path(__file__).resolve().parent
report = run.parents[1]/'reviews/recovery/G-B-R04-api-review-1-recheck.md'
now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
coverage = json.loads((run/'unit_windows.coverage.json').read_text())['totals']
check_names = ['pg_original_and_probes','pg_unrelated_reference','unit_windows','unit_linux','cursor_unit','auth_regression','static_mypy','static_ruff','static_format']
table = []
for name in check_names:
    receipt = json.loads((run/(name+'.receipt.json')).read_text())
    table.append('| '+name+' | '+receipt['started_at']+'–'+receipt['ended_at']+' | exit'+str(receipt['exit_code'])+' | '+name+'.* |')
original_eight = hashlib.sha256((run/'independent_tests/test_review_api_boundaries.py').read_bytes()).hexdigest()
extra_nine = hashlib.sha256((run/'independent_tests/test_review_filters_and_damage.py').read_bytes()).hexdigest()
new_two = hashlib.sha256((run/'independent_tests/test_review_related_references.py').read_bytes()).hexdigest()
contents = f'''# G-B / R04 · PG知识只读API独立复核1

首次创建、本次写作开始/结束与证据截止：{now}。独立reviewer /root/r04_api_independent_review，未参与实现。固定95候选的限定API状态仍needs_changes；初审Must1/3可关闭，Must2原输入已修但同根错误关联仍未关闭。没有签整R04、G-A/G-B或sourcewriter/source_jobs。

What this change does: 修复EventFilters的NUL边界、维度JSON引用成员损坏与不存在ID，以及支持claim的stale传播。默认create_application还挂载来源路由，本复核仅检查它与原知识路由并存后的真实认证读取。

## 固定快照与原输入

实际Git解析 `95ba6503dcae4b86ea8fdffea150f1b59a941014`，tree `25afdc66cbac783fddc748b434a2244d685c96b6`；新干净分支codex/review-r04-api-recheck-20261015，WT `C:/Users/yinha/.codex/worktrees/recovery-r04-api-review-1-recheck/dianzi`。没有复用root可变checkout。AGENTS、恢复R04、03/05、来源持久化CR及只读投影、DTO/auth依据见已封存初审；当前api/domain diff只涉及app.py、knowledge_read_service.py及新的source_routes.py，原auth/DTO未改。

原8探针捕获SHA256 `{original_eight}`，原补测9探针 `{extra_nine}`，与初审字节相同，未改变断言/期待。原24测试copy仅再绑定本人复核库名，conftest仅新WT路径/私密资源绑定和原失败脱敏/实际秘密登记，业务断言未改。41项组合实际全部passed；不能用它们掩盖下面两个新失败。

## Must fix 2 · 仍把可见的错误事件引用当无结果

文件 `backend/src/ai_intel/api/knowledge_read_service.py:541`（541–545）。

- 职责：从保存的维度引用返回对应事件的知识投影，同时隐藏真正不可见输入。
- 触发/事实：创建公开事件A/B及各自公开文档、claim和evidence。先GET B详情和证据均200，确认它们对当前真实认证scope可见；随后分别将A已有available维度的claim_ids或reference_ids改为B的已存在UUID。新存在性检查通过，但因它们不在A的关联修订集合，代码continue；两个输入实际都HTTP200、dimensions=[]，完整响应已捕获。现有DimensionRepository._validate_references在发布时要求证据修订active关联本事件；本次通过测试SQL模拟保存关联损坏，未宣称正常writer产生了此状态。
- 最小修复：对所需ID按同一快照独立做完整来源/修订/对象ACL检查；真正不可见仍隐藏，已可见却不属于当前事件关联修订的对象应抛KnowledgeProjectionError映射503。仅查ID是否存在还不能区分关联损坏与ACL隐藏。保留旧历史修订允许读取的行为，不能把历史正确引用换成新revision。
- 不修影响：公开、可见的保存引用错误仍伪装未取得维度，丢失available/failed状态并遮蔽数据损坏。

新2探针 `independent_tests/test_review_related_references.py` 捕获SHA256 `{new_two}`，两个业务断言均失败；没有skip/删除输入。它们延续初审Must2“错误来源关联损坏需503”的要求，没有改评分、合同、阈值或计分分母。

## 已关闭的原触发

Must1三个HTTP NUL过滤与模型NUL边界均422/ValidationError；既有surrogate拒绝仍通过。Must3支持claim freshness=stale正确传播到维度，同时原event_version/旧revision/withdrawn失效回归仍通过。Must2不存在UUID与三数组[{{}}]已固定503，原嵌套私有来源/维度/claim/evidence仍隐藏，原24中system_admin无tenant、viewer、跨租户404、旧claim不能借新evidence均通过。

## 实际命令证据

原始cwd/完整argv/+08秒起止/退出码/固定SHA/tree/clean状态在本raw目录各receipt，数量见XML。

| 检查 | 实际时段(+08) | 退出 | 日志/收据/XML |
|---|---|---|---|
'''+'\n'.join(table)+f'''

pg_original_and_probes为原24+原8+原9，共41passed，0fail/skip；pg_unrelated_reference为新增2fail，0pass/skip。Windows与Linux全unit各505passed，0fail/skip，原始覆盖{coverage['covered_lines']}/{coverage['num_statements']} statements={coverage['percent_covered']}%，原60门不改。cursor30passed；auth相关security/contract36passed；mypy70源码文件、Ruff全src/tests、format158文件均exit0。保留Starlette/httpx弃用warning，无新依赖消warning。

默认create_application没有显式auth_service注入，只有隔离PG engine工厂绑定；应用自己装真实DatabaseUserDirectory/PgAuthenticationStateStore，cookie登录实际PG状态，两个前缀列表/详情/证据和跨租户/注销cursor均实测。settings=fixture、合成数据明确隔离，不能计live。

本人新DB `test_dianzi_r04_api_review_recheck_20261015`，PG16.14，每例独立schema；无迁移/清理作者库，不downgrade。Windows新WT uv sync --locked真实68包；Linux继续使用本人初审建立、逐项锁版本核对并物理复制的独立Linuxvenv，不共用Windows或作者site-packages。每次COVERAGE_FILE分别在本人仓外cache，两个OS/不同run不相撞。无模型/测绘/PoC/外部资产调用。

自有CBM0.11.0重新索引本新WT backend/src，925nodes/4312edges，70文件、0not-indexed/partial/skipped；仓外独立cache `/tmp/dianzi-cbm-r04-api-review-1-recheck-20261015`，project dianzi-r04-api-review-1-95ba。实际schema、app与auth trace留档，源码rg与default PG HTTP核对cookie→auth scope→PG→DTO。app同时注册source与knowledge两种前缀，POST sources和GET jobs未覆盖三知识GET；此兼容证据不验收source写入逻辑或worker采集。

本人只新增报告/raw，未改业务/schema/锁/progress，未commit/push/accepted。真正阻断为本报告Must2同根剩余；没有用原41/505通过抵消它。资源释放见resource_release.json；私密实际DSN/连接密码/动态认证凭据全文及8片段扫描见private_test_secret_scan.json，final manifest按捕获字节冻结。未读产品keys/.env/KEYS/holdout。

未检：sourcewriter/source_jobs能力与真实worker、browser/live/manual、持续采集、全九维/模型问答、负载性能与并发快照压力、正式金标和整卡/阶段验收。F1/D2/R1只及PG三GET保存知识读取，F2只及所列逐维状态/引用投影，不报满分。

Verdict: fix the remaining Must2 association check first.
'''
report.write_text(contents,encoding='utf-8')
(run/'report_write_receipt.json').write_text(json.dumps({'recorded_at':now,'report':str(report),'code_sha':'95ba6503dcae4b86ea8fdffea150f1b59a941014','original_eight_sha256':original_eight,'original_nine_sha256':extra_nine,'new_two_sha256':new_two},indent=2))
print(json.dumps({'report':str(report),'recorded_at':now,'status':'needs_changes','coverage':coverage['percent_covered']}))
