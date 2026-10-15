# CR-R10 · Vitest安全升级候选

状态：accepted（仅本固定依赖安全修复，按新集成独立意见登记生效；非R01/阶段验收）。
首次创建/本次写作开始时间：2026-10-15T00:23:38+08:00；本次写作结束时间：2026-10-15T00:24:55+08:00。
记录者：主控 /root。授权边界：AGENTS.md §2.5的依赖主版本变动必须记录；本批用户批准CR-R01–09，新重大变更须新授权。

## 问题与可审查候选

当前直接范围Vitest ^3.0.5实际锁定3.2.7；独立审计确认1 moderate及2 critical记录，涉及Vitest和tinypool。不通过跳过审计或隐藏失败处理。
候选固定SHA：497740a771e7cb2d719ab22ebad34bd30539e20d，分支codex/recovery-r01-vitest-candidate；基线d0a179eeb3621cdf21a4cba94a6b5bd4e8a2a120。
产品只改frontend/package.json和package-lock.json：Vitest精确4.1.11及必要传递依赖；React18.3.1、Vite6.4.3、TypeScript5.7.3、Node24运行要求及Playwright1.64.1保持。已有锁缺8传递条目通过正常package-lock-only重建，保留首次ci失败证据，不删锁或force audit。

官方依据：[Vitest advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9)、[tinypool advisory](https://github.com/tinylibs/tinypool/security/advisories/GHSA-5gmw-xhrv-c9v3)、[迁移文档](https://vitest.dev/guide/migration/)。官方修复版本4.1.11满足本机Vite6/Node24，不要求顺带升React/Vite。

## 独立验证与兼容性

新非作者/root/r01_dependency_review复跑33条命令，报告[独立审查](../../reports/reviews/recovery/G-A-R01-dependency-review-1.md)：候选技术通过，不代表正式生效或整R01验收。
实际npm ci、lint、typecheck、build均exit0；npm audit受影响包记录3→0；原30 fixture用例身份完全相同、JUnit30/0失败/0error/0skip。四类运行验证不是累计120个独立案例。
runner仍forks/isolate=true/maxWorkers1/fileParallelism=false，不改任何原验收ID、覆盖率门槛、金标、评分分母或失败样本；没有降标准。新增的会话边界测试另由行为批次审查。
默认GBK输出导致旧冻结quality入口失败已保留；独立UTF8复验通过。主控另有c918279质量修复，最终集成须同时复核，不能拿候选依赖通过背书未合入的质量代码。

## 迁移与影响

批准后主控显式集成候选两份依赖文件及报告证据，执行npm ci、全frontend scope、audit并与当前会话修复合并复核。无数据库/原文/用户数据迁移，产品公开API不变。影响R01/T02工程与前端测试执行器；R17后续浏览器测试仍使用Playwright。
候选未验证真实API/e2e/live/Windows以外全环境、覆盖率provider或未来未知测试布局；这些仍由原任务与阶段门证明，不能计为本单已通过。ESLint弃用警告是非阻断维护债务，未扩大为其主版本迁移。

## 回滚

恢复基线同一版本的frontend/package.json和package-lock.json，npm ci后复跑前端scope；不得只回一个文件。不操作用户未提交文件。应用业务数据不变；回滚会恢复已知漏洞及旧锁警告，因此需要明确记录并停止把审计当通过。原候选与失败/成功原始证据保留。

## 审批与后续验收

历史判断曾记用户授权pending，现经下方独立核对纠正为既有授权覆盖；不是以未回复当批准。独立候选技术意见：passed（497740a固定版本，报告见上）。主控不自签正式生效或accepted；得到新明确授权后登记，并在最终集成冻结版本复核。此前不得将此主版本升级并入本次集成分支或阶段push。


## 2026-10-15T11:49:02+08:00 · 独立核对后的授权解释纠正

原Agent把“依赖主版本须走变更单”扩大成“任何semver major必须新问用户”，这是Agent解释，未生效的人为等待条件。新非作者/root/r02_minio_integrated_review只读核对prompts/12、AGENTS与候选边界，报告[授权核对](../../reports/reviews/recovery/G-A-CR-R10-scope-check.md)确认：本固定测试工具安全修复属于既有完整批次/R01/T02普通工程范围，不是新增产品架构/评分决策。现有明确授权是依据，用户未回复不是依据。保留旧判断/请求/原技术报告，不删历史；本次只取消额外等待，正式生效仍需当前新集成回归与新非作者技术审查。

已将497740a的必要两份frontend依赖文件与471c547前端/已审skip组合为新候选；未引入该旧提交的全部报告或无关attrs。11:47:10–11:47:36当前npm ci/audit/lint/typecheck/完整test/build全exit0，新原始证据recovery_r04_frontend_integrated_20261015；这不是旧30例结论，审计只对这次实际锁文件时点负责。整个阶段尚未验收/push。实际新源码SHA在冻结提交后记录，不虚构本文自身SHA。

## 2026-10-15T13:02:41+08:00 · 当前生效登记

主控依据非作者scope-check与G-B-R04-frontend-review-1-recheck.md登记：既有批次授权覆盖；固定0b983/7f9集成npm ci、115unit、lint/typecheck/build/audit0及浏览器/HTTP专项由独立reviewer复跑。Vitest4.1.11本固定修复生效，旧授权等待判断仅保留历史，不再阻断。此登记不签整R01/G-A或云CI通过。
