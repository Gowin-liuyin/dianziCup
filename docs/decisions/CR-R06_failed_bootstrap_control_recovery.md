# CR-R06 · 启动未就绪时的受控恢复与控制器冻结基线

文档首次创建时间：2026-10-17T04:46:06+08:00
本次写作开始时间：2026-10-17T04:46:06+08:00
状态：approved_for_implementation；新固定实现及实际恢复审计必须由非作者独立核对，不能据本记录签整卡或阶段通过。

## 已证实的问题与授权依据

本次有界批次授权修复真实采集、启动、恢复与资源关闭。冻结 Product `912d8b381eaab9260ead30d68f49b88fa8078384` 的第一次实际启动仅持续 19.816672 秒，guardian 于 2026-10-17T03:34:22.012818+08:00 退出；`runtime_start.json` 尚未产生。API 当时缺少锁定的 langchain_core 依赖，独立修复复核已限定通过；不能据该错误推断 worker readiness 失败的唯一原因。第二次启动在 `configuration.prepare_launch` 读取缺失的 runtime_start 文件时拒绝，尚未启动业务服务。原失败、退出收据与七门登记保留，两个失败都不计作六小时观察。

现有 immutable-freeze 测试要求控制逻辑始终等于 fix3 的旧 Git 字节，仅允许产品与 CORE pins 字面值变化。这项固定快照不能同时容纳本授权要求的失败恢复及类型化 readiness 诊断。旧 74 项命令实测为 73 passed、1 failed；保留旧 oracle 和红记录，不删除、不 skip、不改其断言后宣称旧版本通过。

## 本切片允许的最小变化

唯一作者可以修改控制包中的 `configuration.py` 启动恢复生命周期及 `controlled_supervise.py` 的 `main` readiness/退出诊断。交付必须列出精确文件、函数、Git SHA 和原字节 SHA256。其余十八个控制源码文件保持旧固定字节；旧 AST 白名单外变化、放宽超时、资源预算、来源额度或身份边界均不在本记录内。

缺失 runtime_start 不能视作空 actor 集合或已关闭证明。恢复必须要求 Root 补充真实 kernel closure 审计，并固定到旧 Product、nonce、数据库 OID/COMMENT、实际观察 ID、guardian/source 身份与失败收据。审计只接受固定的非继承 KILL_ON_CLOSE guardian 退出机制、实际 owner/descendant 关闭检查和 MinIO 同 boot/inode 范围关闭证据；argv 扫描、静态 Job flags 或缺失 marker 单独不足以通过。未记录的 actor birth 或 producer ACK 不能补造。

固定旧 CORE `984c270a6240140a82acf875061e9d31d3201d39`、OPS `3c27d6e00a4d31b0821e171bf431fc3ffeaef8fc` 与 runtime binding hash `2a32f6ac2a817c18e2018cafc53f6ea2e39b23684c2772dc094789478a8e6158` 仅可迁移到本次独立审查的精确候选，不接受任意旧 hash。先保存旧 binding、Root gate、授权与失败 marker 的原字节；再安装新固定 binding，并要求 Root 对新候选重新登记门禁。累计 CPU 19.15625 秒、ledger 已用 42/总 450、数据库和历史均不重置；同候选再次失败也必须重新证明关闭。

## 冻结检查、兼容与回滚

新增候选 freeze 测试校验新的精确 SHA/原字节清单，只豁免上述两处明确生命周期变化；它不取代原 73 项行为与安全断言。非作者须复跑原 74 项并说明旧快照为何仍红，复跑新固定 freeze、恢复、拒绝负例和真实 harmless-native readiness 区分测试。若两处之外发生变化，直接 needs_changes。角色身份、PG 权威、租约、原文历史、费用、评分分母、盲测与人工金标规则均无变化。

无数据库或产品 API 迁移，无依赖锁变更。控制器内部诊断增加固定类型的 early exit/timeout 错误，不输出秘密。兼容原正常启动路径及最大运行 21600 秒、关闭 900 秒、固定预算。回滚停止候选并以真实关闭证据确认自有资源终态，再恢复旧固定包及归档 binding；不删除事实、任务、账本或历史。旧包仍存在 failed-bootstrap 缺陷，不能回滚后直接签 ready。

## 影响与验收限制

影响 R01/R03/R06/R20/R22 的启动、持续采集与关闭证据；不改变任何原 T 卡最终范围。先完成非作者控制快照审查及 Root audit，再执行新的实际启动。真实 Source/数据库/MinIO/worker readiness、首轮采集、六小时同版本观察与最终关闭分别记录。harmless native、离线恢复用例和依赖库存不能计为采集 live。阶段 G-C 继续 partial；未发生的新启动、六小时窗口与阶段 push 均 not_run。

## 修订记录

- 2026-10-17T04:46:06+08:00，/root：登记原 immutable-freeze 与已授权恢复的具体冲突；保留旧失败 oracle，限定新的两处控制生命周期变更及独立复验。首次落盘手写时间错误，已按同次工具系统时钟更正；不采用推测时间。
