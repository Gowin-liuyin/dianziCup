"""Record current implementation and honest validation boundaries from the system clock."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
STAMP = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
CR = ROOT / "docs/decisions/CR-R12_default_projection_runtime.md"
REPORT = ROOT / "reports/tasks/R12-default-projection-runtime.md"
assert not CR.exists() and not REPORT.exists()
CR.write_text(f"""# CR-R12 · 默认知识变化索引入口

文档首次创建时间：{STAMP}
本次写作开始时间：{STAMP}
状态：approved_for_implementation；源码与默认运行验证 awaiting_review。
授权：用户完整有界批次、CR-R02/CR-R07 的真实投影、PG权威、受控worker与恢复要求。未改变评测分母、阈值、金标或任务范围。

原默认worker未注册knowledge_change，真实发布后只能blocked/unsupported_job_type。新增retrieval/runtime_policy.py复用HybridIndexer与现有PG租约执行器，默认consumer注册固定handler；输入只从该job绑定的PG change/outbox/tenant读取，不接受请求自报scope或任意URL。

新增HYBRID_GENERATION_ID=e5-v1与HYBRID_INDEX_NAME=dianzi_e5_v1；严格固定代际/索引名，只取服务端配置，模型维度及版本沿用E5 384维。无OpenSearch或固定官方模型缓存明确blocked/corpus_projection_not_configured。新的模型代际必须新建索引并重建，不能把既有成功任务当成新代际重建完成。

单job上限20秒，原worker软25/硬30秒不变；每次原生推理取剩余预算与10秒的较小值，索引写入/最终PG收据提交前检查deadline。未配置模型、原生超时与运行失败分别固定安全码。外部索引只能保存派生数据；查询仍经原HybridRetriever回查PG权限、当前性与epoch。原10000片段容量不放大或截断，超限/超时失败保留，不能假造empty成功。

Indexer派生收据可先于job状态提交；worker中断或租约失效后重试使用同outbox/代际幂等收据。它不提交新的业务事实或另建任务真相。当前仅接混合索引消费者，知识图谱、旧新空结果重判和推荐消费者尚未接：结果必须partial/knowledge_change_other_consumers_pending，不能声称R10/R16已完成。

兼容：旧Indexer caller未传deadline时保持原行为；旧R05单事件问答不改，旧任务、答案、事实与索引收据不覆盖。回滚移除默认handler与新增配置引用、保留派生与历史PG记录；不得用downgrade删除事实。

任务影响：R03/R10/R12/R16/R20、T07/T21/T30/T36–T38。离线装配、deadline正负例及原worker/settings回归通过；真实PG/OpenSearch/ONNX、重启/故障/并发、浏览器/live/manual尚未运行，须新独立reviewer亲复。两次本轮仪器/样式错误原日志保留，原评测合同未调整。
""", encoding="utf-8", newline="\n")
commands = json.loads((Path(__file__).parent / "commands_fix2.json").read_text())
REPORT.write_text(f"""# R12 · 默认知识变化索引切片

文档首次创建时间：{STAMP}
本次写作开始时间：{STAMP}
任务状态：awaiting_review；实现：partial。不是整R12、R10、R16或G-C/G-D放行。
工作分支：codex/full-delivery-recovery。代码编写开始时间：历史未记录；候选源码SHA在冻结后登记。

本轮修改：retrieval/runtime_policy.py、indexing.py、infrastructure/settings.py、workers/runtime.py、直属unit测试及CR-R12_default_projection_runtime.md。复用现有HybridIndexer、OpenSearchCorpusClient、LocalSemanticModels、PG outbox/jobs与Celery，不新增基础设施依赖。新增小factory、限时模型适配与固定handler为默认入口/安全预算所需，未另建事实库。

问题：默认没有knowledge_change handler；配置缺失被笼统标unsupported。现在固定handler已注册，未配置仍明确阻断。完整正向默认worker→PG→OpenSearch链尚未实际验证；partial保留其他消费者缺口。原单次模型10秒若在剩余3秒开始会超总预算，已用剩余预算clip；真正原生超时/故障需独立集成复验。

实际检查：commands_fix2.json逐命令记录cwd/开始结束/exit，最后4命令exit分别{[item['exit_code'] for item in commands]}；public合同28、projection/旧worker/settings 26通过，0skip；Ruff、现有backend配置mypy4源通过。此为unit/contract，不计live。旧跨test import collection exit2、初Ruff4问题及mypy未指定既有配置2import-untyped均保存，修复后的日志使用fix1/fix2后缀，未覆盖原红。

集成/security真实外部/前端/e2e/live/manual：not_run。未使用产品密钥或执行付费请求，无accuracy/recall/P95/6h指标。新schema轮询路径Must另在831c61f修复并由独立reviewer有限Ship，此处public日志不能证明本索引业务。

合同差异与回滚见正式CR。下一步：冻结源码交全新非作者review，使用隔离标记PG库、独立OpenSearch代际和官方已校验ONNX缓存复跑默认入口、失败/重放/重启与当前性；同一阶段尚有其他阻断项，不登记accepted/push。
""", encoding="utf-8", newline="\n")
END = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
for path in (CR, REPORT):
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(f"\n本次写作结束时间：{END}\n最后更新时间：{END}\n证据截止时间：{END}\n")
print(json.dumps({"started_at": STAMP, "ended_at": END, "documents": [str(CR), str(REPORT)]}))
