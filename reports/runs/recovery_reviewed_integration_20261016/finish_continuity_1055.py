"""Finish only the missing fixture step after the preserved continuity assertion failure."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
relative = "reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json"
source = Path("D:/wt/r17-sbom-review1-fix1") / relative
destination = ROOT / relative
raw = source.read_bytes()
assert hashlib.sha256(raw).hexdigest() == "92f5a0cac56ccd97c63af16bd14418cbc1c42cf4803c3ab6627f419235a6e331"
assert not destination.exists() or destination.read_bytes() == raw, "never overwrite a different canonical artifact"
destination.parent.mkdir(parents=True, exist_ok=True)
if not destination.exists():
    destination.write_bytes(raw)
attributes = destination.parent / ".gitattributes"
original_attributes = (source.parent / ".gitattributes").read_bytes()
assert not attributes.exists() or attributes.read_bytes() == original_attributes
if not attributes.exists():
    attributes.write_bytes(original_attributes)
blob = subprocess.check_output(["git", "hash-object", "--path", relative, str(destination)], cwd=ROOT, text=True).strip()
assert blob == "82c40263274fb65517037ab5e3f2d3982f151d67"
for relative_document in ("docs/decisions/CR-R12_default_projection_runtime.md", "reports/tasks/R12-default-projection-runtime.md"):
    path = ROOT / relative_document
    text = path.read_text(encoding="utf-8-sig")
    text += f"\n## 独立审查与修复修订 · {now}\n\n首次 eebee0e 独立报告 D:/wt/r12-default-projection-review1/reports/reviews/recovery/G-D-R12-default-projection-runtime-review-1.md：92回归、31原PG/OS、8生产schema、15默认入口正负例绿；两Must分别22.843秒完整IO超20，以及public10000/tenant1先读无关分区触发SQL57014。真实红保留，不是live/正式指标通过。root修复源码8d62b54d83a3e6b56aeeb23102faa777496328db：成熟httpx.AsyncClient+asyncio.timeout完整headers/body/关闭剩余截止，同源/TLS/认证不放宽，sync保留较短配置timeout；六表ACL及目标分区SQL过滤先于原10001容量探针，逐row deadline检查，10000容量不改。原同步调用兼容、默认生产仅受控worker调用async桥；不新增依赖/事实真相，不动金标/阈值/分母。局部3contract及旧selected22/style/mypy4亲跑过，原始工具输出尚非持久run日志；由原非作者新WT重跑并封存实际证据。真实修复验证awaiting_review，不拿旧绿给新SHA背书；其他knowledge_change消费者仍partial。\n\n修订人/root；本次追加写作结束/证据截止：{now}。首次时间保持原样。\n"
    path.write_text(text, encoding="utf-8", newline="\n")
path = ROOT / "docs/decisions/CR-recovery_0023_0026_integrity_guards.md"
path.write_text(path.read_text(encoding="utf-8-sig") + f"\n## 文档补核修订 · {now}\n\n原独立reviewer附录e94f9d5指出1e210090完整turn guard相同，但没有query函数固定search_path DDL。主控已收窄为生产0024额外加强，非metadata完全对齐。此次仅更正文档，无代码变化；原有限Ship不升级，等待同reviewer文档差异核对。修订人/root，写作结束：{now}。\n", encoding="utf-8", newline="\n")
path = ROOT / "reports/tasks/R18-public-envelopes-output-budget.md"
path.write_text(path.read_text(encoding="utf-8-sig") + f"\n## 原非作者复核修订 · {now}\n\nroot831c61f修poll UUID路径，原23+新5=28和原独立97均通过，独立报告G-E-R18-public-extensions-review-1-recheck.md SHA7682341596be2939452319927ca3ff95f4ed866e72c119ac87356599cbc3390c有限Ship。新schema Git/LF SHA4ccc4337586137a407359a1c4a59dc5d92081a2f4b50ee32cc53fac16095d50b；旧14defs与v2不变。原2非UUID红不改，实际producer/六工具/最终R18仍未通过。首次时间保持，修订人/root，写作结束/证据截止：{now}。\n", encoding="utf-8", newline="\n")
path = ROOT / "docs/decisions/CR-R18_api_key_credential_seam.md"
path.write_text(path.read_text(encoding="utf-8-sig") + f"\n## 锁后时间修订 · {now}\n\n独立真实锁等待跨expiry仍授权Must2，fix2源码8e0485231bf9367d5b4b3a79802bdf346b1fb745。保持公共函数签名、可信server aware now与既有DST注入语义，锁key/users/rate后以单调真实等待推进时间重验issued/expiry/revoked/当前权限，桶分钟变化只在最终桶消费一次；等待后过期事务不消费。复用原PG锁/事务，不另建时钟或限流真相。原20输入/分母保留，新增真实边界及原same-probe红→绿作者已取，原非作者fresh复核尚待。legacy cookie锁前时间仍已知后续R20缺口，不能因此声明全认证通过。兼容回滚保留原记录/迁移，关闭新入口而不downgrade；评分/盲测不变。此次记录追溯当前明确授权，首次创建历史未知不补造。修订人/root，写作结束：{now}。\n", encoding="utf-8", newline="\n")
sdk_cr = ROOT / "docs/decisions/CR-R18_sdk_total_deadline_and_cancellation.md"
assert not sdk_cr.exists()
sdk_cr.write_text(f"""# CR-R18 · SDK整体截止与执行中取消

文档首次创建时间：{now}
本次写作开始时间：{now}
状态：approved_for_implementation；实现/独立审查未完成。
授权：本批R18/T32/T45以及已批准CR-R04/09，落实既有有限资源/完整延迟/取消语义，不削减范围或改评分。

独立实际slow-stream显示原IO timeout=.1仍约.312/.313秒完成，执行中线程只丢结果不能终止IO。现timeout_seconds/question_timeout_seconds保持IO语义及10/100默认；新增operation_deadline_seconds默认10、question_deadline_seconds默认100，合法范围(0,60]/(0,120]，bool/非有限拒绝。整体预算覆盖等待并发槽、headers、全部body及必要解析/清理；单调时钟，不以首字或提交延迟当完整响应。

采用成熟httpx.AsyncClient streaming+asyncio.timeout与任务取消，新增ask_async/check_stack_async/aclose和async context；真实stdio生命周期复用同async client。同步CLI/SDK方法保原签名/typed返回并桥接同真实网络实现，已运行loop调用sync方法要明确可用边界，不能死锁。显式旧BaseTransport测试DI因同步handler无法强杀仅保旧fixture兼容路径，必须显式标识此路径无法证明产品整体deadline/取消；默认真实网络不得进入该支路。新增AsyncBaseTransport DI用于async合同隔离，不计live。共享业务编解码保持单一严格DTO，不复制权限或另一业务真相，不改8000token/1MiB及公开工具语义。

迁移：客户端可选参数兼容旧调用；既有原测试断言/模型/REST合同不改，真实产品默认增实际预算。回滚关闭新客户端入口、保留PG历史，不修改数据库。任务影响R18/R14/R20/R21与T32/T45；需真实loopback慢headers/滴水body/排队和执行中取消、并发4、socket关闭、CLI退出、秘密错误边界及原296/3BaseException/230相关去重回归。只拿fixture绿不签产品取消。报告记录原红、真实耗时、资源关闭和未检项，冻结新非作者审查后才可有限放行。

本次写作结束时间：{now}
最后更新时间：{now}
""", encoding="utf-8", newline="\n")
(RUN / "continuity_1055_receipt.json").write_text(json.dumps({"recorded_at": now, "prior_continuity_assertion_exit": 1, "prior_failure": "archived fixture source path absent; progress already written and not repeated", "fixture_git_blob": blob, "fixture_raw_sha256": hashlib.sha256(raw).hexdigest(), "fixture_restored_without_overwrite": True}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"recorded_at": now, "fixture_blob": blob, "documents_updated": 6}))
