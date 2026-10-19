# G-C / R10 · Neo4j 派生投影初审 1 定向复核 fix2

What this change does: fix2 移除空候选的提前返回，让空结果和非空结果共同复核 PostgreSQL manifest/epochs。无 event IDs 时仍不执行 ACK join；非空候选继续核验可信 PG ACK、immutable batch 与 Neo4j 当前 marker。

**限定结论：Looks good. Ship，范围仅为已批准的内部派生投影切片。** 初审 Must 1/2 及 fix1 复核 Must 3 均已按原输入独立复验关闭，没有新增可复现 Must。不签完整 R10/G-C/R20、默认产品入口、正式0025或live/manual；没有修改 accepted/progress。

## 冻结与保护核验

新干净 WT `D:/wt/r10-neo4j-projection-review1-fix2`、分支 `codex/r10-neo4j-projection-review1-fix2`，代码冻结 `707331add19f3f8eed4ba530305113028d3caedb`，最终材料 `e8e4086fccc2d9c3f2f582f85e185f5b6f395f0b`、材料 tree `2a20e50bd91bf88c68ecf00a1938855e149cab34`。固定输入为 fix1 最终材料 `28a35f16ad1ebe08a49b63126b2c6fc828607333`；没有复用作者工作目录。

阅读 fix2 作者报告、实际 frozen_code_verification/raw manifest/镜像屏蔽清单与源码 diff；AGENTS、00、03/04/05、R10/R12/R20、T21/T29、原实施合同及 fix1 范围补充继续适用。沿已读取 ponytail-review 5.2 的源码与真实 caller 流程审查，没有用文件名猜出不存在的额外合同或扩大公开语义。

独立亲核作者 fix2 manifest raw SHA `313ec07323e8aa2ea8e108c1bdbe97b36de4308310cad90c1a89371b43229e47`，ZIP SHA `66804358f1a1db15ab6f7c65393c7ba9cb6a5ab93da5e3009ea079ac426d6216`，55成员 raw hash/长度逐项匹配。初审68成员ZIP及 fix1 复核55成员ZIP亦逐项匹配；原 fix1 作者58成员由受保护 Git 原对象保留。原11 probe SHA `6d8565c06cb64bd8bacbdb8aff81dfc3908842088cd0eec17094dc835b959cf1`、原epoch2 probe SHA `3e1e767d7c01ee18b02888c56509676dfa020c5b79d8a8506b7afc216b83ae09` 从封存ZIP恢复原bytes，仅换本审查资源namespace，输入/assert不改。

13005个输入受保护原 Git 对象逐一一致；唯一业务修改是 graph_projection.py 的条件ACK join和共同末尾检查，另加 Sequence 类型及必要格式缩进。其余 owned source、原五测试、fix1 tests、shared/auth/policy/settings/锁/迁移/attrs/规则/容量/金标/分母未改。CODE→最终材料的 backend/src/tests 无变化。三源码 raw/LF哈希与重算 Git blob匹配：graph_projection=`aa37e2d922d2b0e7089e6ae0309ba201adfa000e`、neo4j_projection=`1c5fb137f289ff27fcddeef85019d5cc0aca9dbe`、models=`42a76f699bcaa8fabee2adb7ef9843e3d14cfce0`。[独立输入核验](../../runs/recovery_r10_neo4j_projection_review1_fix2_20261016/input_verification.json)

独立CBM自有缓存刷新为1730 nodes/9183 edges，schema、qualified候选trace及rg实际调用点均exit0，辅助结果与源码互证。默认API/producer/registry/frontend仍没有此模块caller，不能把内部Ship解释成产品已接通。

## 原 Must 的输入、结果与关闭依据

| 原项 | 保留的实际输入 | 本冻结结果与源码依据 |
|---|---|---|
| Must 1：技术marker/PG ACK hash围栏 | Neo4j坏digest/float marker；slot+edge同时异hash但PG ACK不变；PG ACK hash/bool/float/batchref、错身份以及合法restore | 全部按原断言通过。Neo4j严格INTEGER/non-null/positive、active/hash与namespace/partition/generation/event/canonical key；PG限定401行join对照可信已ACK slot与immutable batch，再检查manifest/epochs，未以派生库自身hash相等代替PG权威。 |
| Must 2：缺epoch分类 | 实际PG缺public epoch；missing/zero/bool/negative；未知ConnectionError | 缺epoch立即固定state blocked、attempt1、ACK0/store0；未知IO保持4次retry_wait后failed。只在投影epoch验证边界分类，shared executor/授权不改。 |
| Must 3：空结果跳过IO后epoch检查 | 真Neo4j查询在返回前另一真实PG事务bump public epoch，True有候选/False空结果两参数不变 | 两参数均ProjectionNotReady；[`graph_projection.py:939`](../../../backend/src/ai_intel/knowledge/graph_projection.py#L939) 的空rows + `if event_ids`只控制ACK查询，[`graph_projection.py:1011`](../../../backend/src/ai_intel/knowledge/graph_projection.py#L1011) 的共同manifest/epoch复查覆盖两分支，无空结果提前返回。 |

最终PG当前事实、ACL、支持与hydrate围栏仍是主控caller的责任，`requires_pg_revalidation=true`保持；这里关闭的是内部技术一致性问题。

## 真实命令与结果

入口为 `D:/dianzi/backend/.venv/Scripts/python.exe -B reports/runs/recovery_r10_neo4j_projection_review1_fix2_20261016/review_runner.py <name> <arguments>`；pytest cwd固定本WT/backend，使用`--import-mode=importlib --no-cov`和仓外cache/basetemp。各同名JSON保存完整精确argv/cwd、真实+08起止、exit、耗时与实际输入文件SHA；未把局部覆盖率当全仓门。 [JUnit汇总](../../runs/recovery_r10_neo4j_projection_review1_fix2_20261016/junit_summary.json)

| 组 | 实际结果 / exit | 原始证据 |
|---|---|---|
| 原132首轮 | 130 passed /2 setup errors /exit1；failures0、skip0；110.41s | regression_132.json/log/xml |
| 同132顺序复跑 | **132 passed /exit0；failure0/error0/skip0；87.15s** | regression_132_sequential.json/log/xml |
| 原epoch2定向 + 自写3边界 | **5 passed /exit0；failure0/error0/skip0；21.67s** | probes_boundaries.json/log/xml |
| 三owned source strict mypy | exit0 | static_mypy |
| 三source与fix1/fix2三专属测试 Ruff/format | exit0/exit0，6files | static_ruff/static_format |
| 固定 source/test/report diff check | exit0；历史raw空白exit2不重写 | git_source_diff_check |
| 新CID只读kernel/ownership/截止 guard | exit0，09:03:11+08当前快照匹配 | resource_caps_root、kernel_security.json |
| 当前真实metadata/auth与自有收尾 | exit0，Community5.26.32/driver6.4.0/usage=false，错误凭据拒绝，自有schema0 | neo_cleanup、resource_cleanup_receipt |

132=原97+原11+fix1新增17+原epoch2+fix2新增5；作者另一次17复跑不计新用例。定向5中2是上述132内的原epoch2复跑、3是本reviewer新边界，不能把132+5宣称137个唯一用例。

本reviewer额外三绿：真正零事件/零页的ready manifest，在实际Neo4j返回稳定空候选；缺失generation在外部IO前阻塞；另一合法generation在查询IO内完成capture/apply但epoch不变时，所选原generation仍按自己的PG ACK返回，其新generation亦按自己的hash读取，未因正常分区独立写入制造冲突。这不验证主控尚未实现的active-generation选择策略。

原132完整保留六关系、当前支持/权限、tombstone/withdrawal、2001support/8MiB拒绝、101事件完整manifest、旧空→新增、history、竞争worker/乱序/重复、Neo4j commit后PG rollback、逻辑Session/adapter恢复、server故障rollback、可信Session/context authorizer、payload伪scope拒绝与有界未知IO重试。输入supports均synthetic，真PG/Neo4j不是第三方业务live。

## 环境红、身份与秘密

首轮最后两个输入校验案例在fixture连接PG25432时报`FATAL: too many clients already`，业务尚未开始；没有改断言/skip。根与R07遇到相同资源症状，主控限制重PG并发最多2，本reviewer停止自身并行PG组后顺序复跑同132。首错误及日志完整保留，不混成业务失败，也不改PG上限、生产pool或kill他人会话。两个setup阶段遗留schema仅在本审查精确数据库/owner/marker与`test_r10r1f2_<uuid>` guard下清理；cleanup engine已dispose。

仅fresh own PG `test_dianzi_r10_projection_review1_fix2_20261016`，run/schema长度均符合guard；未使用作者/旧review/collector DB。Neo4j仅新 `r10_review1_fix2_<uuid>` namespace/generation；列出并严格核对59个自有namespace后逐一固定参数删除，未触他人namespace、未全图wipe/重建DB或volume。所有own测试进程退出，fixture/cleanup/metadata engines及drivers释放，已向root发release ack，不再占重PG batch槽。

当前exact CID `2cbf8058a220f4b3bc0d4da779f06ddaa314f7a87feeac32ab64b18d0735bf99`、owner/boot/创建/process身份、volume inode701675、memory1.5GiB/swap0/CPU1/pids128、六caps bounding0xeb/tini有效0xeb/Java有效0、seccomp2/no-new-privileges1及仅loopback27687/27474均亲核。原deadline `2026-10-16T19:35:43.312788+08:00`不延；本批没有stop/restart/服务生命周期操作，不代签资源graceful-stop或R20运维。

上一轮我保存的epoch红日志中SQLAlchemy Engine repr漏屏蔽PG登录用户名，密码仍为遮罩；此轮已在own conftest适配中把实际用户名作为SecretStr登记，runner与最终raw/JUnit/报告扫描也核对用户名。原外部raw及55ZIP保持不动，作者fix2的新用户名屏蔽mirror与原路径/hash清单已核验。上一轮DSN/password扫描0不能回溯宣称用户名也已屏蔽。

当前DPAPI仅在pwsh7捕获获准字段到内存，使用正确NEO4J_TEST_*，实际DSN/password/PG用户名不放argv/报告/rawenv。所有当前日志/JUnit及整个ownrun/report的实际值扫描为0；只在两个owned工具内分类主控给定的完整公开基库常量上下文，移除该完整常量后仍须0匹配，不排除整文件或其它位置。共享failure hook未改。

一次生成owned封存helper的shell引号SyntaxError为exit1/0tests，未访问资源或改业务；改用apply_patch创建本reviewer工具，错误另列instrument_helper_failure。该最初工具错误未捕获精确起止，显式null，不编造时刻。旧KeyError/旧probe仪器红、原业务红与raw whitespace历史都保持原证据。

## 范围与交接

本reviewer只新增own报告/run/probe/资源适配，未改业务/shared/progress/accepted/attrs/locks/0025/publicAPI，未commit/push/spawn。F2/P2/E1证据支持内部派生投影的完整清单、可重放提交与当前技术围栏；A1/GraphRAG/多跳答案与完整阶段评分没有新增声明。

root先核验并归档本报告、固定代码/材料、原红和当前raw，再安排合并及共有接线。内部有限Ship不解除正式0025/default producer/catalog/outbox/registry/taskauth、active generation、API PG current/ACL/支持/hydrate和前端责任。

Not checked: 默认产品API/正式0025与down/生产恢复、frontend/e2e/多跳、第三方来源/provider/model live、6h监测、manual、规模性能与服务graceful关停；这些仍另验，不签整R10/G-C/R20。
