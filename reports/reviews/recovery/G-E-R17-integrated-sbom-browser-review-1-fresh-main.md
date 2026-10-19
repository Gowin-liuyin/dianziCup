# G-E / R17 · 主控集成 freshGit 资源闭合附录

What this change does: 本附录只核验已审 SBOM 五个源文件及原测试资源在主控集成版本中的精确身份，并从新的干净检出直接复跑前端检查。它没有新的产品代码、资源适配器或业务验收范围。

**结论：原首审的 freshGit 资源缺口在主控 `8514ebb16fedfe026cc280b78fced993af1dc5e8` 已闭合；限定 Ship 仍仅覆盖 R17 SBOM 工作台切片。** 新工作树直接执行原557/557、lint/typecheck/build均通过。原 `f1f2` 的549通过＋ENOENT失败证据保持，不追写成旧候选自包含；整R17/T40–T44/G-E仍partial，作者awaiting_review与进度不由本审修改。

- 原非作者评审人：`/root/r17_actual_backend_sbom_browser_first_independent_review`；未参与实现、未spawn。
- 新独立工作树 / 分支：`D:/wt/r17-main-sbom-fresh-proof` / `codex/r17-main-sbom-fresh-proof`。
- 本附录受审主控HEAD：`8514ebb16fedfe026cc280b78fced993af1dc5e8`。
- 主控五文件集成提交：`d74765b1500457bff31bf20fb170c6b26abd9ea4`；原资源提交：`6be1d1b2f2101bea58b488531dbfb1f83fcdc0ce`。
- 原产品源码：`4a17fa3fb7357a8c2b9d647f62c875958a24a27d`；主控基线：`17ab90e0a6b100530a3078dd525f9086813c9728`；原前端材料：`5587deb124f06b9aa14fb7feb22cdc9493ae4883`。
- 原独审报告冻结：`aac5780b101f01e3a3f4d3427ce8a112653223bc`；原Git原件补证：`92c809004c65a62e517fd2ef598f2e32a32da0b0`。原报告raw SHA256 `70aed583674be26ea4a26e2ac2f610ab6275193a33f6a9b37ac61434e8ba514c` 本轮前后相同，旧工作树clean，没有改原报告、原红例或原材料。

本轮再次读取当前AGENTS、00执行索引、R17恢复卡与task_state中的R17状态；沿用已读Ponytail review5.2及原R11/资产/SBOM/权限合同。task_state仍列R17 in_progress/partial，与本切片有限结论一致。

## 精确身份与资源闭合

本人从8514创建新工作树，其初始git status为空。五个SBOM文件在8514与4a17的Git blob相同；原58个test/spec在8514、5587及17ab的集合与blob均相同。逐文件证明在 own run `fresh_source_audit.json`，没有修改原测试、金标、分母或测试期待。

fixture原路径 `reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json` 直接来自Git：blob精确 `82c40263274fb65517037ab5e3f2d3982f151d67`，检出raw SHA256 `92f5a0cac56ccd97c63af16bd14418cbc1c42cf4803c3ab6627f419235a6e331`，27787 bytes。原run-local `.gitattributes` 的Git内容、8514内容和本检出raw精确相同；fixture未被Windows换行归一。原八条serializer期待的后端material仍为5be873，未重新生成金标。

本轮无copy/mount/link test resource，也没有沿用前次node_modules junction：在本WT执行锁定 `npm ci --ignore-scripts --no-audit --no-fund`，实际安装299包，然后从本WT运行原完整suite与本WT构建。八个serializer案例作为合成合同留在557内，不升格为live或新的端到端证明。

## 实际直接复跑

下列cwd均为 `D:/wt/r17-main-sbom-fresh-proof/frontend`。人类时间+08:00；精确argv/cwd/HEAD/resource_adapter=false/start/end/exit在 own run 同label `_command.json`，原stdout/stderr在`.log`。工具起始建WT/读文件/恢复自己的buildinfo没有单独结构化完整起止，只保留会话工具输出，不补造。

| 检查 / 实际命令 | 起止 | exit / 实际数量 |
|---|---|---|
| install：npm.cmd ci --ignore-scripts --no-audit --no-fund | 11:34:10.927–11:34:15.830 | 0；299包，非业务测试 |
| unit_main：node node_modules/vitest/vitest.mjs run --reporter=json --outputFile=own/unit_main_result.json | 11:34:34.957–11:35:10.931 | 0；557pass、0fail/pending/todo/suite error |
| lint：node node_modules/eslint/bin/eslint.js . | 11:34:34.929–11:34:42.880 | 0 |
| typecheck：node node_modules/typescript/bin/tsc --noEmit | 11:34:34.934–11:34:39.730 | 0 |
| build：npm.cmd run build | 11:34:57.038–11:35:02.089 | 0；本WT生成dist |
| audit_fresh_source.py：精确Git/raw资源及受保护scope核对 | 11:34:10.892–11:34:21.581 | 0；5source＋58oldtests＋original fixture/attrs |

本次无失败或skip。npm原whatwg-encoding/eslint deprecated提示保留，没有改锁版本来消除提示。质量检查不是业务测试，不累加进557；前次真实9browser也不与本轮557混为新计分分母。

## 后端与新增迁移的边界

相对4a17，资产模块、资产原0018和SBOM原0022迁移、默认`api/app.py`、`api/authentication.py`、`api/auth_state.py`、角色权限`domain/access.py`及前端assets目录/依赖锁均无Git差异。该结果为保留原首审默认API/PG0022/Edge九例的源码身份依据，**本附录没有再次执行PG或Edge**。

仅作简单迁移依赖与模型diff核对：新增0023 enrichment audit →0024 conversation context →0025 graph projection →0026 api key credentials，0023继承原0022；两张资产metadata与原0018/0022均未变。实际diff原文在 own run `migration_model_scope_diff.log`；auth_state差异文件为空。未运行新0023–26链的数据库升级/业务联测，不能由本轮前端通过背书其正确性；主控后续阶段整体联测另批。新主控其他模块的实现、性能、权限、连续运行或全平台验收也没有获本附录结论。

## 保存与范围

只新增本附录和 `reports/runs/recovery_r17_main_sbom_fresh_proof_20261016/`。业务/progress/accepted、原报告与原run无改动，没有push。本轮不读取DPAPI或秘密参考、不启动服务、不占重PGslot、不访问外部资产或付费模型。own run局部 `-text` 只保存本审raw收据/日志字节，不修改原资源attrs或共享检查配置。

主用户 `D:/dianzi/frontend/tsconfig.tsbuildinfo` 全程只读，所有receipt前后SHA256仍 `3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d`。本WT自己的生成buildinfo在检查后恢复HEAD；最终protected frontend/backend/docs/progress/contracts工作树diff为空。

Not checked: 本次PG/Edge重跑、新0023–26数据库升级、其他主控模块、外部真实SBOM/模型/FOFA/VEX/Agent、正式评分/性能/持续运行、人的manual与连续录像。

Verdict: **Ship，仅R17已审SBOM切片；8514 freshGit原557直接复跑闭合。** 原首审真实本机九例按其4a/默认0022范围保留，原f1f2红不删、不回写；全R17与阶段验收继续按原合同推进。
