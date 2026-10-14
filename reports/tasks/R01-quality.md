# G-A / R01-quality · 真实质量入口与测试隔离

文档首次创建时间：2026-10-14T22:53:01+08:00。
本次写作开始时间：2026-10-14T22:53:01+08:00；本次写作结束时间：2026-10-14T22:59:03+08:00；最后更新时间：2026-10-14T22:59:03+08:00。
实现Agent：/root/r01_quality。独立review：未运行；工作包状态：awaiting_review。
分支：codex/recovery-r01-quality；输入冻结基线：69ecf16be7d95e839b18a4a40f03b3f9d86707f4。
当前证据为自检中的工作树，尚未签R01/原T02/T03，也没有阶段push。

## 1. 范围与前置

R00准确落实由独立review accepted后主控派发。本包实现R01/T02检查入口与R01/T03安全测试接通，E1/R2证据；认证/API/worker/基础设施/锁/CI/前端实现由其它唯一所有人负责。

已读AGENTS、执行地图、R01/T02/T03及架构/测试/编码/运维合同，采用本机Ponytail插件5.2.0 full。没有删原C01–C06，没有修改金标/阈值/分母。

## 2. 修改与复用

- scripts/dev.py：七scope真实派发；pytest/Vitest/Playwright使用实际JUnit testcase元素计数，0项、失败、error、skip、报告缺失均非通过；unit保留既有cov60，contract/integration/security沿用既有scope门槛。all全部层执行后汇总，不用首层成功代替全部。
- 前端层执行既有npm lint/typecheck/test/build；e2e要求真实test:e2e入口及JUnit，不借组件测试冒充浏览器业务。
- subprocess有1–3600秒参数边界；超时终止本次进程组/Windows子树，exit124；工具缺失/测试资源缺失exit4。未知scope/错误参数exit2，未建设exit3。
- 公共测试guard限定TEST_DATABASE_URL的PG、loopback、test_dianzi_<run_id>、test_用户及独立端口；5432仅显式container隔离且用户=库允许，CI=true不是豁免。查询参数、fragment和非test库拒绝，错误不回显连接串。
- backend/tests/conftest.py：共享隔离fixture，导入/collect-only不联网，执行期才探身份/迁移；缺资源以error/blocked呈现，删除旧skipif。pytest报告hook只脱敏DSN/密码，不改结果/count；真实故意失败证明终端/JUnit不泄漏且仍exit1。
- T03生命周期在写数据/restart/down前校验正在运行的自己Compose服务/项目/POSTGRES_DB；不操作当前裸Docker资源。WSL Docker前缀只接JSON argv，Windows文件转/mnt路径，不shell/eval、不改全局context。Compose config只在内存捕获，避免回显环境。
- T05/T07及contract/T07删除硬编码常规DSN/导入时端口探测，保留原业务断言。T05额外downgrade回路改为非破坏性重复upgrade/版本不变；原C06既有事实/时间/unknown保留仍在，不执行破坏性downgrade。
- T02类型错误注入改用pytest临时目录，不往src写临时文件与其它Agent竞态。未建设scope负例在明确空目录验证，不依赖未来e2e是否存在。

复用现有uv/pytest/pytest-cov、npm/TypeScript/Vitest、Docker Compose及标准库subprocess/XML/URL解析。没有新增依赖或通用测试框架；增加的IO控制、隔离guard、报告脱敏和共享fixture是完成验收与秘密保护所必需。

## 3. 调用方与版本定位

codebase-memory-mcp官方portable v0.11.0；本WT独立project=dianzi-r01-quality-wt，cache=/tmp/dianzi-cbm-r01-quality-wt-20261014，索引仅scripts，不包含秘密/holdout。
初始3文件82节点251边；修改后89节点285边，main到scope/Compose调用链实测并与rg交叉核对。记录cbm_receipt.json/index/trace于本包run目录。生产业务不import脚本；共享guard仅开发CLI和测试使用。后续冻结与合并须刷新对应tree索引。

## 4. 实际自检与证据

日志目录：reports/runs/recovery_r01_quality_20261014/。每个receipt记录真实命令/cwd/开始结束/退出码，XML记录真实用例；不把基线SHA冒充工作树代码已冻结。

| 检查 | 真实结果 | 限制 |
|---|---|---|
| 初次目标检查 | 41 passed（30新负例+11T02） | 初稿探索，后来新增到32负例 |
| unit | 47 passed，cov61.73%，exit0 | 输入基线业务源码，非后续API新版本证明 |
| 32质量负例 | 32 passed，exit0 | 真实timeout、真实失败报告脱敏、无IO导入；待冻结再复跑 |
| offline_recheck_1 contract | 104 passed/1 real_pg显式deselected/0skip，exit0 | 明确fixture子集，不是完整contract/live |
| 初批完整contract | 102 passed/1 setup error，exit1 | 百分号迁移根因，保留失败日志 |
| 初批PG T05/T07 | 1纯文件 passed/20 setup error，exit1 | 下述主控库授权纠正；迁移前失败，无业务写入 |
| security | 20 passed，exit0 | 既有fixture安全测试，非默认应用新鉴权验收 |
| frontend | lint/typecheck/test1/build，exit0 | 旧骨架，仅1组件测试，不等于UI业务完成 |
| e2e | exit3 not_implemented | 本基线无test:e2e，真实UI由另一Agent接入 |
| missing resource integration | exit4 blocked | 不skip、不SQLite |
| all无资源 | exits unit0/contract4/integration4/security0/frontend0/e2e3；总exit4 | 证明失败/阻塞传播，不是all通过 |
| Ruff/format/mypy | 最新自检exit0；mypy48源文件 | 原失败及修正记录保留，冻结后仍需复跑 |

初次uv sync发生TLS handshake EOF（exit1），随后锁安装成功；npm ci既有锁成功，报告damaged lockfile警告及3漏洞(1moderate/2critical)，没有擅自--force改锁，已通知锁所有人主控。早期未归档命令精确起止为历史未记录；不推测补写。

各层状态：unit passed；contract partial（fixture passed，完整PG失败待复验）；integration blocked/未完全复验；security passed仅fixture；frontend passed仅旧骨架；e2e blocked/not_implemented；live not_run；manual not_run。

## 5. 问题与纠正

| ID | 触发/预期/实际/根因 | 修复与状态 |
|---|---|---|
| Q-01 | 原dev.py contract/frontend/e2e/all不存在；scope实际运行不可证 | 新真实入口/JUnit、0/skip/失败负例，已修待独立review |
| Q-02 | 原测试import联网并skip，硬编码5432/ai_intel，T05在开发库downgrade | 移除import IO/默认DSN/skip；隔离guard+fixture；非破坏迁移验收，已修待review |
| Q-03 | 原health以healthy子串判断unhealthy也命中 | 精确JSON Health/State检查，负例passed |
| Q-04 | ConfigParser set_main_option未转义URL百分号；fixture带%3D options在迁移前ValueError，含编码密码同受影响 | 已报告主控唯一数据库所有人，root公共修复待SHA与本包专库复验，不私自测试层绕过 |
| Q-05 | 初次派发授权读取主控r01_20261014配置；22:38以后身份SELECT成功、迁移进入DB前失败 | 主控随后明确每WT独立库，立即停止复用；本包新runID=r01_quality_20261014/PG25434/Redis26381，复跑脚本必须核对身份。首批不是合格隔离验收，没有down/restart主控实例或写业务数据 |
| Q-06 | pytest fixture异常把参数DSN带入终端/失败XML | 报告脱敏hook+真实故意失败负例，结果仍1failed；历史XML精确替换实际test秘密，原失败保留 |
| Q-07 | Windows mypy不识别POSIX os.killpg/SIGKILL，初稿static失败 | sys.platform分支，最新mypy48files passed，未ignore |
| Q-08 | 初稿Ruff两unusedvar及长行，早期root目录uv找不到ruff | 用backend锁环境、格式和修正，最新Ruff/format passed，不掩盖初稿错误 |

## 6. 环境输入与复验入口

TEST_DATABASE_URL/DIANZI_TEST_RUN_ID必填；TEST_REDIS_URL/TEST_OPENSEARCH_URL附属服务loopback独立端口。
DIANZI_DOCKER_COMMAND_JSON是可信本机Docker argv前缀；DIANZI_TEST_COMPOSE_FILE是Windows侧可读文件，DIANZI_TEST_COMPOSE_PROJECT必须dianzi-test-<run_id>；dev服务必须DIANZI_COMPOSE_PROJECT显式dianzi-dev/test前缀。

私有配置只在仓库外由主控/资源Agent注入；不打印DSN/密码、不复制connection.json入仓库。复跑run_checks.py需DIANZI_TEST_CONNECTION_FILE指定本WT私有WSL路径，核对r01_quality_20261014，每次创建新recheck目录而不覆写历史失败。

本包未购服务，无产品模型/测绘API调用，产品API费用0；编码Agent费用unknown。T03真Compose生命周期、OpenSearch、浏览器e2e、业务API/worker及live均等待对应真实输入/实现，不能用已有资源smoke签整卡。

## 7. 下一步与交付

等待主控公共百分号修复的冻结SHA，按本WT专库复验PG/默认contract；冻结代码由新独立reviewer复跑32负例、原T02及资源边界，主控集成后重跑全scope/真实UI版本。报告只awaiting_review，不accepted，不push。没有新增计划/评分差异；本包不签整原T02/T03或G-A。

## 8. 冻结复验与文档修订

2026-10-14T22:59:03+08:00：代码/首稿报告已冻结2b79c8087ee49bf6c6926359fab793977f3d6117；独立review尚未运行，已审SHA无。作者在此冻结源码复跑32质量负例passed、47 unit passed/cov61.73%、mypy48源文件passed、8授权源码/test的format passed；命令/精确时间/退出码/日志在frozen_2b79c80/。这是冻结源码自检，不是初稿基线或完整R01通过。

secret_scan.json核对9个提交文件及当时全部本包证据：两套已授权test DSN/密码未发现残留；没有读取产品密钥。后续PG仍等待主控共享迁移百分号修复冻结SHA，使用本WT独立资源；T03真Compose生命周期/OpenSearch/e2e/live保持未通过。

## 9. 新公共实现与本WT真实PG复验

本次写作开始时间：2026-10-14T23:33:23+08:00；本次写作结束时间/最后更新时间：2026-10-14T23:48:13+08:00。首创建时间不改。root公共实现a874c2752af7746bf70ede7bd203f62a2840d68c通过cherry-pick在本WT为ebedb39af5367a25fcaff199a2bf290c2385f23d；增加默认认证/API、settings、锁、迁移百分号修复，不能拿旧源码测试背书新实现。

资源fresh探针：WSL true exit0/0.141秒、Docker version exit0/0.469秒、自己loopback25434/26381可达；receipt按实际start/end与wall_clock_seconds记录于fresh_resources_20261014_2334，不将此前宿主其它Agent异常860秒称为本包正常timeout。没有restart/delete/root资源修复。

新冻结公共源码自检日志recheck_20261014_233550：unit47passed/cov62.00%保留60门、quality contract32passed、完整contract107passed(含1真实PG T07合同及2迁移URL配置)、T05/T07文件21passed(20真实PG fixture+1纯文件安全例)、security28passed；全部0fail/0error/0skip。Ruff/format/mypy49源文件和默认scope contract均exit0；使用本WT专库test_dianzi_r01_quality_20261014/PG25434，没有复用root库。百分号缺陷由root公共修复，本包没有业务层绕过。

完整integration也实际执行：38passed/3failed/0skip/exit1；三失败是T03真实Compose依赖/重启/down-up，缺DIANZI_TEST_COMPOSE_PROJECT被guard在IO前拒绝；其它14内存判断测试仍按unit语义，不计真实PG能力。未提供自己Compose+OpenSearch，不能从裸Docker资源或21目标例通过签整T03/T07/R01。

锁安装：新npm ci exit0；本WT只有旧骨架App，尚未取得frontendAgent组件/e2e配置。初次scope frontend因旧node_modules缺node types exit2；锁安装后lint/type/test实际成功，build的Unicode✓输出又触发本包dev.py GBK stdout编码缺陷(exit1)，这是检查入口bug，不是构建业务失败。新修复仅main标准库TextIOWrapper设置UTF8/安全errors；新增真实ascii/gbk CLI中文help负例，质量负例34passed、mypy49文件passed；待新freeze复跑受影响scope。e2e当前0tests/exit1，Playwright误发现旧Vitest组件文件，无真实浏览器流程，明确未通过。

## 10. 新证实的R03阻断（不改本包公共业务）

2026-10-14T23:48:13+08:00：job_boundary_probe.py在自己真实PG的合成逻辑时钟/回滚事务复现两项失败，exit1：schedule_retry_or_fail后同逻辑时刻立即重领(actual true/expected false)；lease60秒后+61秒原owner complete仍成功(actual true/expected false)。源码workers/jobs.py:32 retry_wait无到期条件/无next_retry_at，:90 complete与:115 retry只校验owner/job_id，缺有效租约/状态校验。所有探针SQL事务回滚，未留下业务数据；不是墙钟持续运行测量。共同根因和触发/lines/最低复验已通知root，由R03统一修复退避与租约/fencing，不能把21旧正例通过当这些边界已通过。日志job_boundary.json/stdout。

各层最新状态：unit passed；contract passed(完整107，新增stdio负例另34passed待freeze复跑)；integration partial且完整命令failed/资源缺口；security passed仅fixture/HTTP隔离；frontend/e2e未完全通过；live/manual not_run。本包只awaiting_review，R01/G-A没有通过、没有push。

## 11. 编码修复冻结与最终自检

2026-10-14T23:53:12+08:00：Windows输出修复已冻结c918279c003925844c2444b768a2c81e427ffb33。作者在此源码再次跑：34质量负例、47 unit/cov62.00%、完整contract109、T05/T07文件21(20PG+1文件)、security28，0fail/0error/0skip；Ruff/format/mypy49files和默认scope contract exit0。frontend已从新锁npm ci，scope实际lint/typecheck/Vitest1/build完整exit0，Vite Unicode输出不再失败；这仍是此WT旧骨架组件，不是主控新UI验收。e2e0tests/exit1保持未通过；missing resources integration exit4。完整integration的3个真实Compose缺口仍未关闭。新日志recheck_20261014_234925，每条命令具有code_sha/实际起止与退出码，旧失败全部保留。

scripts索引按c918刷新及main trace成功，命令单10秒deadline、实际exit0/墙钟记录于cbm_index_c918/cbm_trace_c918，范围仍仅scripts，排除秘密/holdout。无独立review结论，已审SHA无；工作包awaiting_review，R01/G-A没有accepted/push。最后证据commit只包含本包report/runs，并携带root明确授权的2条rawXML attrs(已经在c918代码commit)，不引入其它公共配置变更。
