# R10 · Neo4j 投影 fix2

状态 `awaiting_review`；本轮剩余 Must 修复 `complete`，完整 R10/G-C 未验收。WT `D:/wt/r10-neo4j-projection-fix2`，branch `codex/r10-neo4j-projection-fix2`，固定输入 `28a35f16ad1ebe08a49b63126b2c6fc828607333`；代码冻结 `707331add19f3f8eed4ba530305113028d3caedb`。无push/accepted、progress或共享模块修改。

## 最小修复

唯一业务修改 `backend/src/ai_intel/knowledge/graph_projection.py` 的 read_projection_candidates：空候选不再提前返回；没有event IDs时跳过ACK join，有候选保持原限定401行join和逐项ACK校验，之后共同复核manifest/epochs再返回。只补Sequence类型注解和必要缩进，无新接口/依赖/规则/容量/错误码。

新增专属 `backend/tests/integration/test_r10_projection_fix2_empty_reads.py`：稳定ready空结果可返回空；未ready在外部IO前拒绝；空seeds/bool hops/未知relation在外部IO前拒绝。最终产品PG current/ACL/支持/hydrate、0025/default API/producer/registry均仍由root负责。本轮未改另外两owned source、全部旧tests、policy/auth/epoch producer/settings/locks/migrations/attrs/主仓。

## 原输入与调查

原reviewer已只读交接新两参数probe：原bytes SHA `3e1e767d7c01ee18b02888c56509676dfa020c5b79d8a8506b7afc216b83ae09`，1695 bytes；原55成员ZIP SHA `ce2728db0520810676c5619fe1b2c43280332b9ea51ebdc9008809d0ce48c1c5`、manifest SHA `c1fda01ce43f206eccb638803ecdff97076fa1a83ddaa3ef2271cee3e3590751`逐成员核验。原red json与log/xml的凭据屏蔽镜像见本run/review_input，镜像清单记原外部raw路径/SHA；原外部raw/55ZIP保持不动。输入、True/False、真正Neo4j查询→另PG事务bump→return和断言保持，只替换fresh ownnamespace。原fix1的58成员ZIP/hash与全部历史红保留在输入Git树，未覆盖旧WT或材料。

源码首改前独立CBM index/architecture/schema/read候选qualified trace与rg actual callers检查均exit0（见cbm/rg JSON）。只索引backend/src，自有缓存在仓库外；未读env/KEYS/盲测答案。仍无默认API/producer/registry/frontend caller，不能据内部修复声称产品接通。

## 实际验证

统一入口 `D:/dianzi/backend/.venv/Scripts/python.exe -B reports/runs/recovery_r10_neo4j_projection_fix2_20261016/fix_runner.py <name> <python args>`；cwd固定WT/backend。各JSON记录精确argv、真实+08起止/exit/耗时、输入与3源码磁盘SHA。继承code_sha/materials_sha描述输入版本，实际运行以source_head/source_file_sha256核对本代码冻结；raw ZIP保护原bytes，LF规范SHA另列，不混称。

| 检查 | 真实结果 | raw证据 |
|---|---|---|
| 原2参数probe baseline | 1 passed/1 failed，exit1，空分支原红保持 | probes_red.json/log/xml |
| 修复后原2参数probe | 2 passed，exit0，5.71s | probes_green |
| 原125+原2+新5合跑 | 132 passed，exit0，86.12s，skip0 | regression_final.json/log/xml |
| strict mypy三个owned source | exit0 | static_mypy_final |
| 最终ruff/format修改source+新test | exit0/exit0，2 files | static_ruff_final/static_format_final |

原125继续覆盖权限负例、六关系、bool/float/hash/身份、PG ACK、缺epoch公共blocked code、unknown IO有界重试、旧空→新命中、容量8MiB/2001supports、complete manifest/current watermarks、历史、竞争/重复、Neo4j commit后PG rollback、Session/adapter逻辑恢复及server fault rollback。新空/nonempty epoch移动均被拒绝，稳定空未误伤。原单事件2000/200/400与8MiB预算、relation语义、schema、金标、分母不变。

初次新增if缩进导致两处行宽与format检查exit1，原log保留，规范format后最终静态检查绿；未禁用工具或改门槛。测试使用--import-mode=importlib稳定适配独立资源，targeted --no-cov不当全仓coverage门通过。

## 隔离、秘密与限制

仅fresh自有PG `test_dianzi_r10_projection_fix2_20261016`，run ID `r10_projection_fix2_20261016`，marker `dianzi:r10_projection_fix2_20261016:owned-test-only`；创建前强guard基库/127.0.0.1:25432/test_ role与实际身份，不存在才建，已有owner/marker不符即拒绝。每项 `test_r10fix2_<uuid>` schema只清自身；未接原作者/reviewer/collector DB/事实/Redis/OS/队列。

Neo4j只获准既有资源、own `r10_fix2_<uuid>` namespace/generation，实际官方driver6.4.0与Community5.26.32。root已交新CID `2cbf8058a220f4b3bc0d4da779f06ddaa314f7a87feeac32ab64b18d0735bf99`/cap0xeb，原deadline `2026-10-16T19:35:43.312788+08:00`不延；作者未stop/restart/delete共享图。服务代际重启及graceful-stop属于另外资源owner/独立review，本文只记录该代际下业务回归及逻辑重建，不签运维通过。

DPAPI只在pwsh子进程捕获获准TEST_DATABASE_URL及NEO4J_TEST_BOLT_URL/USERNAME/PASSWORD/resource_id/deadline到内存；实际密码/DSN经共享conftest SecretStr hook，raw/JUnit/报告实际值扫描0，不放argv/报告。PG用户名若与root给定静态基库常量有子串重合，仅允许runner该完整公共guard上下文，其他位置不排除，实际登录用户名不回显。

封存初检发现原reviewer的新red log/xml含SQLAlchemy Engine登录用户名，pwd为***；只在内存识别，未回显值。原外部raw与SHA保留，新材料仅用户名屏蔽mirror，不改probe/断言；仅删除本作者刚复制的两份未提交重复件，未删原red或旧材料。初检分类与mirror manifest留据，本轮原红、132日志无此问题。

unit/contract/security/真实隔离PG+N4 integration/static已跑；source/input支持显式synthetic，不算第三方live。frontend/e2e/provider/model/来源live、manual、生产migration/down/rollback/default caller与规模性能均 `not_run`。G-C/整R10/A1/GraphRAG无新增验收声明。

交付source/protected Git树、原输入、manifest/raw hash与秘密0留于 [本轮run](../runs/recovery_r10_neo4j_projection_fix2_20261016/)。root取得代码/材料freeze后交原非作者reviewer按原probe复核；作者不自签。

交付核验：13005个原保护对象不变；code tree `dfbcf7c5e569d76d0dce4e5d2ffc0d4d444cb4e4`。132 JUnit failures/errors/skipped均0，工作区cache目录为空；source/test/report diff check exit0，全raw staged diff exit2仅保留原输出/检查日志空白，不改raw或属性使其伪通过。
