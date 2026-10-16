"""Record the approved attempt-local verified-content boundary with actual writing times."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
path = ROOT / "docs/decisions/CR-R16_completion_fanin.md"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
body = f"""
## {started} · 本次执行内的 VerifiedContentReuse 与调用方兼容

本次写作开始时间：{started}
授权记录：主控已在本批派单冻结以下内部边界，消费者新非作者须核 source d550c8232b5e8b46550941c513db5aba04078308；公共端口 968c71b6 的四参数/None 兼容签字不代签消费者。

使用私有 frozen JobExecutionResult 子类携带本次真实 verified bytes/proof，不改共同端口，不建 global job/cache map。证明绑定 job/worker/attempt/tenant/精确 Actor/request SHA。handler 必须通过原 AssessmentService.read 与 ContentStorage.read_verified/原 SHA 检查取得真实原文；冻结只读 Mapping 和不可变 bytes 后，final guard 仅重放同 hash 字节、复用原 load_rule_inputs 算法重建全部当前 PG 证据、权限和语义，再比 input_digest/epoch/rule fingerprint/asset snapshot。缺 hash、新 hash、错 context、停止或超限明确 blocked/partial，不回读外部 MinIO、不用 None 假 store、不用 PG metadata 代替原文。该证明只是此 attempt 的内容寻址观测，不跨重启或成为另一套事实权威；lease 丢失未调用 guard 时随执行结果释放。

去重缓存总上限 64MiB，沿原 R11 每对象 2MiB/每规则 8MiB 较低限；新 hash IO 前核 PG size 与缓存总预算，最多本页 100×20 次有界引用读取。超限 explicit partial/verification_budget_exhausted，不改变原 page/model/tool/评分分母。read-only 重放 store 的 store/delete 拒绝；原文 bytes 不经 repr、JSON、日志或公开结果输出，不声明外部对象存储掉电/篡改恢复已证明。

依赖读取提取同原 actor owner/digest 的无依赖 job FOR UPDATE 路径，保留实时 credential/scope 校验、读后重读状态与 immutable binding 校验；当前执行 job 的 lease/guard 事务锁完整保留。此举避免 continuation B→completion C 与执行 C→parent B 的 job 锁环，不能放松 ACL。

既有 test_page_budget_preserves_blocked_owned_continuation 的一处实现指针按新不可变父 completion 引用解析 manifest.next_page_job_id 后，仍精确检查原 continuation blocked/cursor/not_claimed。原完整字节和初红归档，不改变 two-types 或其他 Oracle。原 drive outcomes 只允许 succeeded/partial 的另一个调用方尚未真实验证，新增 retry_wait 可能触发；保留原断言，必须先实际复现，再精确协调原 harness 的重试驱动，不用排序/删样本规避。

验证新增范围：真实字节与 tamper/缺 hash/size、缓存边界/不跨生命周期、repr/日志边界、同 job 重放/lease 丢失/owner/actor/source 变化、旧/新/空 cohort、continuation 与真实 PG 并发/晚到。作者 194 离线/85 新只是自检，三 PG 仅 collect；新独审前不得 accepted 或称完整 R16。回滚关闭新 completion 生产，保留 PG 历史与旧请求/父结果；无表或公共 schema 迁移。
"""
with path.open("a", encoding="utf-8", newline="\n") as document:
    document.write(body)
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
with path.open("a", encoding="utf-8", newline="\n") as document:
    document.write("\n本次写作结束时间：" + ended + "\n")
(RUN / "fanin_proof_contract_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": ended, "path": path.relative_to(ROOT).as_posix(), "consumer_source": "d550c8232b5e8b46550941c513db5aba04078308", "whole_task_accepted": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"recorded_at": started, "whole_task_accepted": False}))
