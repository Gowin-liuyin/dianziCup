"""按实际时钟登记冻结切片和缺口，保留历史，不自行验收整卡。"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
STAMP = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
HEAD = "60fe4c311f98a0692e2207b884d83b676f5fb9c2"
summary = f"""## {STAMP} · 当前冻结与并行快照

集成分支codex/full-delivery-recovery，实际HEAD {HEAD}，origin=https://github.com/Gowin-liuyin/dianziCup.git；没有阶段push。R00 accepted；R01/R02仍needs_changes/partial，R03独立网络包开始，G-A未过门。旧记录保留，不能将下文旧时点当当前事实。

- UI准备源码80d7c1b（作者fa57874/00a5c99/bb3a3b3）已集成；独立初审P2键盘跳转错误由bb3a修复、90da冻结复核64组件+2匿名真实键盘通过。动态背景像素可见和reduced-motion停止有初审真实浏览器证据；原生hidden暂停仍manual未证实。整R17不是accepted；R04列表/详情/证据独立前端仍在实现，业务API尚未接通。
- R02知识初审四项Must fix保留：同事件第二CVE、版本分支/评分authority/ecosystem误supersede、模型假设借dispute进入事实、pytest局部凭据泄漏。root33423b4修前三并真实PG回归30通过，8015ac0给真实session_hash语义名；TLS/隐私源9a696b7已经集成但组合复核未发生，不能先关闭问题。
- MinIO源码60fe4c3：官方SDK7.2.20、两种真实存储适配器共享协议、配置选择无本地后备、默认严格TLS，仅APP_ENV=test容许明文。135纯unit通过/cov63.21%；172单元+真实MinIO/PG知识/关系回归通过/cov74.13%，11:19:13–11:19:34；11:20:29–11:20:31实际服务PID4244→18956后字节一致。它们是隔离资源integration，不是外部来源或模型live。新批次awaiting_review，原API/worker业务尚未接线。
- MinIO是官方固定源v0.0.0-20251015172955-9e49d5e7a648构建，二进制自报DEVELOPMENT.GOGET，不能冒称官方发布二进制；官方server仓库已归档的维护风险保留。源码构建10:56:34–11:08:35，1GiB/1CPU，无OOM；服务11:15:28开始，唯一自有cgroup768MiB/.5CPU/256PID、7200秒总上限、仅127.0.0.1:29400，独立private root600凭据。存储备份/产品TLS/最小权限服务身份/旧对象迁移还未验证。
- R03网络实现/root/r03_network_gateway独立WT recovery-r03-network从8015ac0；只network/http_transport与本包测试/报告，不改root公共迁移/锁/settings/状态。R02未复核问题不被网络内部开发依赖，不能据此签整R03。前端/root/hacker_frontend只src/e2e并对齐099c5b1读投影合同，401身份generation fence须回归；新review槽待冻结MinIO/组合持久化批次。TLS作者已交回CI/conftest，未再占共享容器。

当前关键路径：独立复核持久化/隐私，补维度持久化与0010前向迁移，真实任务/PG游标和受控网关，接R04两源/API/浏览器；再真实模型。0009的输入fingerprint唯一不够表达失败重试的新结果，必须前向修正不能编辑已应用迁移。模型/测绘凭据已授权且保存在仓外秘密管理；尚未调用产品模型/供应商，费用unknown。CR-R10 major升级仍未获新授权，FOFA范围/双人金标缺口仍在，PPT后置。运行曾02:47→09:51宿主中断，结束时点unknown，不能计连续采集。

"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"):
    target = ROOT / relative
    target.write_text(summary + target.read_text(encoding="utf-8"), encoding="utf-8")

report = f"""# R02 · MinIO原文存储冻结切片

文档首次创建时间：{STAMP}
本次写作开始/结束/最后更新时间：{STAMP} / {STAMP} / {STAMP}
主控实现：/root；状态awaiting_review；实现partial；整R02/G-A未验收。代码冻结{HEAD}，前置9a696b7；没有push。

## 范围与实现

R02/T05的对象适配切片，复用现有PG内容对象/修订/父行锁/事务、SHA256接口和官方MinIO SDK7.2.20；新增最小ContentStorage协议、可信配置工厂与远端实现确有两种IO语义，未重写知识层或建立第二事实库。原StoredObject内部Path接口保留，远端只返回hash/size。固定bucket、哈希键、限64MiB和超时、TLS默认严格、无SDK重试、先读验hash/再写/写后验证才登记PG，缺失与拒绝/网络/服务错误分开。settings选minio配置不全就启动失败，不能悄悄回退本地。工厂已在真实PG修订测试调用；默认API/worker业务仍未接入，R03/R04继续完成，不能以测试路径冒称产品闭环。

## 实际问题和验证

- 初次unit SDK错误样本用了不符真实S3Error签名的fixture，124passed/1failed；按真实SDK签名修fixture，125passed/cov62.70%。原unit_first/unit_sdk_error_fixed日志和XML保留，未把失败skip。
- 加配置工厂后纯unit135passed/cov63.21%，原60门未降；该命令起止未单独捕获，JUnit原始工具时间保留，不能拿文件mtime编造。mypy57源exit0；Ruff首轮6项、格式后3项已修到exit0，静态完整记录待冻结复跑。
- 真实隔离PG r02_knowledge_20261015+MinIO测试bucket：11:19:13–11:19:34，`uv run --locked pytest tests/unit tests/integration/test_r02_minio_persistence.py tests/integration/test_r02_knowledge_revisions.py tests/integration/test_r02_relation_identity_regressions.py --junitxml=<private temp> -q`，172passed/0failed/0error/0skip，cov74.13%，1warning保留。包含独立进程新客户端、A→B→A三版、新PG连接、rollback不发布、真实对象损坏拒绝覆盖、真实拒绝与missing分别、存储断线不提交、两线程同版。cwd D:/dianzi/backend；实际参数和原始计数见real_first.command.json/log/xml。私有临时XML写前/传出脱敏，未提交秘密。
- 自有原文服务实际重启11:20:29–11:20:31，PID4244→18956，同hash读取字节一致，见restart_verification.json与两个service_segment收据；不是mock、不是全系统备份恢复，也不是正式性能数字。

## 资源和限制

官方Go下载checksum、构建固定模块/Go sums、真实二进制hash均见本run。实际server源码v0.0.0-20251015172955-9e49d5e7a648，Go1.27.2构建二进制自报DEVELOPMENT.GOGET，不能冒称发行包；官方仓库归档维护限制保留。SDK新增pycryptodome/urllib3用于真实S3签名/HTTP，未替换整栈。测试只有root身份、明文loopback、独立bucket；产品TLS/最小权限/部署镜像与备份、旧本地对象迁移尚未验证，不能称production可用。resource上限、7200秒截止、实际启停时间见service收据；无付费API，模型费用unknown。

## 验证分层与下一步

unit=passed（本切片135）；contract=not_run（新配置边界在unit）；integration=passed（真实资源172混合范围）；security=not_run（专门审查尚未发生，含部分边界不替代全层）；frontend/e2e/live/manual=not_run。新独立review应冻结60fe4c3并复跑关键7个MinIO/PG案例、坏凭据/损坏/回滚；顺带核对已集成33423b4/8015ac0/9a696b7的初审Must修复和原生失败隐私，不能只读作者日志。整R02仍需维度持久化、发布幂等/重放与最终独立结论。

本报告结束：{STAMP}。真实未来审查、提交、push时间必须另记，不回填此时尚未发生的结果。
"""
(ROOT / "reports/tasks/R02-minio.md").write_text(report, encoding="utf-8")

stage = ROOT / "reports/stages/recovery/G-A.md"
text = stage.read_text(encoding="utf-8")
for prefix in ("本次写作开始时间：", "本次写作结束时间：", "最后更新时间：", "本报告证据截止时间："):
    text = "\n".join(prefix + STAMP if line.startswith(prefix) else line for line in text.split("\n"))
text += "\n\n## " + STAMP + " · 追加冻结与问题复核记录\n\n" + summary + "\n本次仅快照修订，首次创建时间未改；已有通过范围不自动背书新代码，整阶段继续in_progress/partial。\n"
stage.write_text(text, encoding="utf-8")

state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
state["updated_at"] = STAMP
state["updated_by_task"] = "R02/R17 checkpoint; awaiting independent integrated review"
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"updated_at": STAMP, "code_sha": HEAD, "stage_accepted": False}))
