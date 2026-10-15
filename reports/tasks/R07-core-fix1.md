# R07 · 类型账本初审三项修复

文档首次创建时间：2026-10-16T00:12:20+08:00
本次写作开始时间：2026-10-16T00:12:20+08:00
本次写作结束时间：2026-10-16T00:12:20+08:00
最后更新时间：2026-10-16T00:12:20+08:00
实现者：/root；阶段G-C；工作分支codex/r07-core；状态awaiting_review；整卡实现partial。
固定已测代码SHA：ce1da8811495f1ea1de538c67cb12b16e6d8a280。初审代码74d8e9ba8b49360ca90ade390f7b6c00cd40b815，完整材料bf660e8a20f606225b1dd881faaeaf9bfc3550b3。
独立初审：/root/r07_core_independent_review，G-C-R07-core-review-1.md，结论needs_changes；本修复待同一独立reviewer定向复核。未集成、未push，不能以作者测试签accepted。

## 真实问题、修复与影响

1. 初审版本区间同时fixed/last_affected、仅branch等输入被运行模型拒绝，但导出JSON Schema接受。VersionInterval的json_schema_extra增加已有上界互斥/至少一个来源边界的组合约束，保留省略/null合法差异，重新生成schema_bundle。
2. 初审文献目标仅document或仅revision身份被运行模型拒绝，但导出schema接受。LiteratureReferenceValue导出同时省略/null或双方UUID组合规则，运行行为保留。新合同10例第一次原代码4failed/6passed保留；修复后10例全部通过，没有修改期待使之变绿。
3. 初审public文献claim可内嵌其他tenant私有目标UUID，其他租户读取公共claim能获得目标身份，未证实正文泄漏。KnowledgeRepository._validate_submission现在查目标修订与文档真实配对，执行现有enforce_visible，并限制派生claim范围不得宽于目标。7例真实PG覆盖公有→私有、跨租户、错误配对拒绝且表计数/epoch不变，以及public/public、同租户和私有→public允许及重放。

复用Pydantic JSON Schema扩展、现有PG事务/权限/范围函数与声明模型；没有新依赖、迁移或认证变更。只修改domain/enrichment_values.py、knowledge/persistence.py、schema_bundle、新contract/PG测试和CR-R07_typed_signal_claim_v3附录。旧v1/v2、旧DTO和未注册谓词规则不改。回滚与迁移见同一变更单：有v3数据后必须保留读取层，不删历史。

## 实际验证

run：reports/runs/recovery_r07_core_fix1_20261015。cwd/实际argv/起止/版本和dirty状态见每个JSON；原60%完整覆盖门未改，--no-cov仅为定向检查。

| 命令标签 | Asia/Shanghai起止 | exit | 真实JUnit数量 |
|---|---|---|---|
| core_fix_frozen_format | 2026-10-16T00:01:55+08:00 → 2026-10-16T00:01:55+08:00 | 0 | not_test |
| core_fix_frozen_mypy | 2026-10-16T00:10:01+08:00 → 2026-10-16T00:10:02+08:00 | 0 | not_test |
| core_fix_frozen_pg | 2026-10-16T00:01:20+08:00 → 2026-10-16T00:01:54+08:00 | 0 | tests=41, failures=0, errors=0, skipped=0 |
| core_fix_frozen_ruff | 2026-10-16T00:01:54+08:00 → 2026-10-16T00:01:54+08:00 | 0 | not_test |
| core_fix_frozen_unit | 2026-10-16T00:01:16+08:00 → 2026-10-16T00:01:19+08:00 | 0 | tests=87, failures=0, errors=0, skipped=0 |
| core_fix_mypy | 2026-10-15T23:56:57+08:00 → 2026-10-15T23:56:59+08:00 | 0 | not_test |
| core_fix_schema_unit | 2026-10-15T23:56:22+08:00 → 2026-10-15T23:56:25+08:00 | 0 | tests=87, failures=0, errors=0, skipped=0 |
| core_fix_target_pg | 2026-10-15T23:56:26+08:00 → 2026-10-15T23:56:57+08:00 | 0 | tests=41, failures=0, errors=0, skipped=0 |
| schema_boundaries_red | 2026-10-15T23:54:50+08:00 → 2026-10-15T23:54:54+08:00 | 1 | tests=10, failures=4, errors=0, skipped=0 |

冻结后87定向unit/contract与41真实PG全部通过；41=原13新结构+7目标权限+原catalog21。Ruff/format/mypy95均0；mypy在冻结后另跑并保留。unit/contract/integration/security仅本片passed，frontend/e2e/live/manual=not_run。0来源/模型/测绘请求，费用unknown。
PG使用独立test_dianzi_r06_catalog_r07_core_fix1_20261015，run_id=r06_catalog_r07_core_fix1_20261015；每例仅新UUID schema，迁移0015，只清理自己schema，未使用生产库或downgrade。新库隔离避免其他WT同库advisory lock争用，未改业务锁。

CBM对固定ce1 backend/src独立索引、get_graph_schema、完整限定名_validate_submission出向均exit0，cbm_commands.json记录；排除秘密/holdout/reports，源码及新负例交叉验证。没有将图边当作业务正确证明。

## 限制和下一步

候选接口仍不是九维自动产品链；来源loader/语义验证/最终发布/worker/API/UI、真实模型与公开信号live尚待后续。原初审关于继承int coercion、未检查生产多修订证据链等边界继续保留，不把其误称本片修复。先由独立reviewer在固定ce1复跑3项触发输入/正例和相关回归后，才允许合入限定账本切片。

## 修订记录

2026-10-16T00:12:20+08:00 /root首次创建；初稿红例、脏树初测、冻结后复测与独立初审均保留，不覆盖原74d报告。

2026-10-16T00:12:39+08:00 封存首次git diff --cached --check exit2：原JSON receipt为CRLF，-text保全后被视为行尾空白。只在本run的*.json登记whitespace=cr-at-eol，保留原bytes；没有改源代码或原日志。任务报告统一LF后计算制品hash。

2026-10-16T00:12:59+08:00 第二次封存字节检查发现运行helper check_core_fix.py原CRLF与Git自动LF不同，停止提交。仅对此证据helper登记-text与cr-at-eol，不放宽业务*.py规则。

2026-10-16T00:14:50+08:00 新独立只读/root/r07_evidence_bytes_diagnosis定位Git index缓存未因新属性重算：helper工作树5101bytes含132CR、index4969bytes为LF，stat相同普通add未刷新。采用唯一精确git add --renormalize -- .../check_core_fix.py，原helper/日志/全局autocrlf不改；复核所有暂存字节后封存。
