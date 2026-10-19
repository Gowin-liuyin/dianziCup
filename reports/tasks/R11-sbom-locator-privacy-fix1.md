# R11/T24 · SBOM locator 隐私修复

状态：awaiting_review；实现切片 complete，整 R11/T24/T28/R17 保持 partial，未自签 accepted、未 push。工作树 `D:/wt/r11-sbom-locator-privacy-fix1`，分支 `codex/r11-sbom-locator-privacy-fix1`；冻结基线 `6aeeeec5489b92bb49613fe5daa4eec379182348`，源码提交 `9b22adfeb918e9bf1ee4862935bcaa6dd3f1ea88`，tree `1ea22f139a8ad48ccebc8e37a882105ae7c956b0`。材料提交由交接消息给出，不把自引用 SHA 写入本文件。

本轮输入是合法 CycloneDX 未知 JSON 键和已冻结 SBOM 展示载荷，输出是安全、稳定的逐段 JSON Pointer 或现有安全 503。仅修改 `backend/src/ai_intel/assets/sbom_inventory.py`，新增专属 `backend/tests/unit/test_r11_sbom_locator_privacy.py`，以及本报告和独占 run。未修改 parser、DTO、schema、inventory service/routes/app、迁移、依赖、认证、前端、属性文件、progress、金标或计分门槛。未运行下载 PoC、访问第三方资产、调用付费服务。

开始前读 AGENTS、00_execution_map、12 中 R11/R17、03/04 合同、CR-R11_sbom_inventory_proposal、CR-R11_sbom_sidecar_table、adapter/default-reader 合同及状态/交接。主工作区存在未提交修改，因此从冻结 6a 创建独立工作树，未清理或覆写用户文件。应用 Ponytail full 5.2.0；授权只覆盖这两个已确认安全 Must 和直接调用方回归。

## 原始证据和实现

新非作者 reviewer 的冻结原探针文件 SHA256 `7e26ef18e236f915447e413784adf8b650b69d257db31afd004a2bebedebd62d`，原 default_http_v2.log SHA256 `43a35d596348adbd3198e7351bbaafbc587a1e2846ab61ca0b970387fc55d56a`，原 XML SHA256 `d72e581e89c54080389fd2f11fc9b146c5760c9833ea1eaf1244693aa3f15ac7`。原文件只读复制为本 run/original_probe_frozen.py；新运行的资源适配文件只改变独占数据库绑定，并由 root 批准对测试 fixture 自有 engine 指定 NullPool，所有探针输入和业务断言保留；没有执行原 runner 或写原目录，也未 patch 默认 App/build_engine。

原 25 探针在本自有测试库 08:57:35–08:57:48+08:00 实际 22 passed / 3 failed，exit 1。M1 的两个合法未知键分别为 `../../private/sbom.json` 和反斜杠路径：真实 POST 201、GET 200，响应透出 private/sbom.json。M2 将同作用域快照、原文和 hash 绑定完整复制到新编号历史行，以合成坏 schema2 locator 和同位置 None marker 验证事故边界：GET 预期 503，实际 200。该历史只由自有测试夹具写入，不主张远程客户端具有任意 PG 写入能力。

最小同输入 unit 于 08:58:23–08:58:25+08:00 为 3 failed，原红保存。更早 original_minimal_red 用 `-k original` 误选了 encoded 原键 hash 测试，且 placeholder 测试最初仍包含无关私有 ref marker，得 4 failed / 3 passed / 44 deselected；改为没有无关 ref 的合成载荷，精确三条红已单独记录。首轮扩展 locator 测试误认为未知 opaque 对象会递归索引到 public-child，实际冻结 parser 只定位该未知对象根；保留 locator_unit_green1 的 16 failed / 94 passed，纠正自建测试的错误 oracle，并另外手工构造历史嵌套 locator 验证安全父段、数字索引和子段不变。没有改既有测试/金标或删边界。

源码增加共享 JSON Pointer 转义和字段安全判断，最多四轮严格 percent/UTF-8 解码沿用原实现。所有 typed locator 和 redaction locator 都检查每段；在确切服务器 marker 允许的完整 `redacted-field:64 lowercase hex` 段后继续检查剩余段。相对斜杠/反斜杠路径、dot 段、绝对路径、控制、非法/未消解编码、userinfo/URI scheme 键不透出。普通 Unicode 键、numeric 索引、合法安全 PURL 键保留。HTTP URI 展示判断未改，也没有扩大网关读取白名单。

新/schema1 未知危险原键按 JSON Pointer 反转义后的原字节 SHA256 生成既有 redacted-field 标记和 reason=unsafe_uri_or_path、replacement_ref=None，不合并不同编码原键，不改拓扑、raw、fullJSON/combined/projection hash。客户端字面量恰好是生成前缀仍按原键重新 hash，避免位置碰撞。schema2 历史须满足整段格式、规范转义、精确位置、固定 reason 和完整 replacement pair；重复、缺失、多余、错误格式或后续危险段 fail closed。错误文字固定且不包含敏感 input/raw cause，复用现有 GET 503 边界，不伪造 mask-success。

第一次业务修改前实际 WSL portable `--help`、source fast index 1819 nodes/9955 edges 和独立 assets full index 261/1175；source 图排除了 assets，因此追加独立 assets 图，未把无边当作无调用。trace 和源码 rg 确认 safe_sbom_sidecar → freeze → import，同函数也由 GET 历史读取在 scope/hash 校验后调用 → DTO → 现有 frontend assets（冻结候选未接 SBOM UI）。初始探索工具没有逐项秒级 receipt，不补造；日志保存顺序和基线已明确。冻结后独立 full assets index/trace 有真实 +08 秒级命令收据。

## 测试与范围

所有 pytest 使用实际解释器 `D:/dianzi/backend/.venv/Scripts/python.exe`，实际 cwd 为本 WT/backend，`PYTHONPATH` 强制当前 WT/src；完整 argv、起止、退出码与 head/tree 见各 label.json，原 stdout/JUnit 与 test_counts.json 见 run。全部 pytest `--no-cov`，不声称全 suite coverage、性能 SLA 或正式准确率。旧报告 547 是此前独审分母，不能拼凑或相加；本轮按原 337 和迁移 pure 文件去重得到实际 616 条相关回归，original_regression547 只是早期请求沿用的 label，数量严格按 XML 为 616。

| 范围 | 实际结果与时间（均 2026-10-16 +08:00） |
|---|---|
| 原默认 API 25 首红 | 08:57:35–08:57:48，exit 1，22 pass/3 fail |
| 最小原 Must unit 3 首红 | 08:58:23–08:58:25，exit 1，3 fail |
| 首冻结9b22 locator unit：新增 55 + 既有 33/26 | 09:04:48–09:04:50，exit 0，114 pass |
| 首冻结9b22 相关 unique pure/contract/security | 09:04:19–09:06:11，exit 0，616 pass，0 fail/error/skip；一条既有 cookies deprecation warning |
| 冻结默认 API 原 25 串行复验 | 09:07:10–09:07:20，exit 0，25 pass，0 fail/error/skip |
| 新默认 API schema1/schema2 历史和重启 18 | 09:01:16–09:01:30，exit 0，18 pass；冻结提交前运行，后续仅增加空白/userinfo 字段判断与 marker membership set |
| 原库存生产迁移 head 105 | 09:01:54–09:02:27，exit 0，105 pass；冻结提交前运行，原函数和断言未改 |
| 原生产迁移 119 首轮 | 09:01:35–09:02:51，exit 1，117 pass/2 fail；资源配置问题见下文 |
| 独占空迁移库 119 重跑 | 09:04:20–09:06:09，exit 1，61 pass/58 errors；PG 连接数资源阻塞 |
| 冻结 API25+历史18+原库存105 合并运行 | 09:04:38–09:05:52，exit 1，101 pass/1 fail/46 errors；PG 连接数资源阻塞 |
| 冻结全 src mypy | exit 0，146 source files，无 Any/cast/ignore |
| 源码/新 unit/harness 风格和格式最终检查 | exit 0；初始长行、import order/type loop 变量冲突均保留原红并修正 |

上述范围有重叠，不把重复测试合计为新通过数量。unit/contract/security 的实测与相关 integration 边界分别记录；前端/browser_e2e、外部产品 live、人工真实资产核验均 not_run，完整 R11/T24/T28 和阶段不升级。

原 119 首轮没有继承既有 R05_SEMANTIC_CACHE，真实模型案例明确 blocked_live；同时默认 API 的 public schema 已前向 0022，使回滚测试的未限定 to_regclass 沿 search_path 命中 public 已有表，随机 schema 自身的 DDL 已回滚。仅新资源 harness 指定既有已验证模型 cache 和另建自有空迁移数据库，无 schema/business/断言变化，未下载模型或执行 downgrade。

重跑空库迁移与合并 API 并行后真实 PG 报 FATAL too many clients already，导致 58 setup errors 与 API 46 errors/1 OperationalError fail。没有把不可达写成业务通过，也未增加 max_connections、杀其他连接、扩大超时或补产品代码。全部子进程已自然结束、runner Engines 显式 dispose；09:07:20 冻结 API25 单独串行复验通过并明确向 root release。本轮遵守 root PG admission，随后获得 root 单 slot，严格按默认25→历史18→原库存105→空库119逐组执行。每组子进程退出后，自有数据库剩余连接计数为0；最终全部通过。资源红保留，不能据此前 too-many 自动推断默认 App shutdown 泄漏。

## 秘密保护、兼容与交接

只从指定 DPAPI 文件通过明确 pwsh7/Python capture 内存取得 TEST_DATABASE_URL，没有打印/env dump/argv 密钥，不连接原库写数据。自有数据库名、资源 marker、截止时间 2026-10-17T21:49:15+08:00 和实际 PG/vector 版本在资源 receipt；没有删除数据库、改生产或 downgrade。默认 API 使用真实 cookie 登录、认证作用域和生产 run_migrations(head)，禁止 MetaData.create_all/business Table.create。全部上传/事故历史均 explicit synthetic fixtures。

共享 SecretStr failure hook 明确装入：实际 DSN/password、测试随机密码/session/CSRF 均登记，失败输出/JUnit 受保护。每次 PG run 的原字节 exact DSN/password 扫描为 0；最终扫描覆盖本 run、源码、新 unit 和报告，用户名相同短前缀按每个路径/行列出语法分类，不 blanket ignore；任何未分类用户名命中会阻止 seal。credential_scan/source_proof/artifact_manifest 及 exact-raw tar.gz 保留原红、真实命令、原探针和源字节，使 Git LF/CRLF 转換不冒充原材料精确 hash。材料由本 run seal 后交独立复核；精确 manifest/原字节和原红均保留。

迁移兼容：不新增 DDL/回填，不重写不可变 schema1/schema2 历史或 raw。新/schema1 输入安全投影；旧 schema2 中未处理路径、残留危险段或不一致 marker 由新 reader 503 fail closed。历史 GET 不重跑 parser、不以新算法覆盖旧结论。回滚必须保留安全 reader 或停用 SBOM/sidecar 展示，不能恢复旧透传 reader，也不能删除原文、历史表或变更 current。

F2/F3 证据仅为声明安全显示、引用位置保留、原始版本/hash 和租户边界；E1/D1 为实际原红、复跑、类型/风格、秘密保护与完整证据绑定。未产生 P2/P3 正式指标，不改分母或误差，未完成整体评分要求。

下一步：封存 source/material/exact hash 后，原非作者 reviewer 在新 WT 定向复核两个 Must 和新边界，root 决定是否集成。不自行 accepted/push。

未检查：前端/浏览器、外部 live、人工资产完整性与整个工作台；普通业务自由文字不属于本 locator/URI 显示修复范围。

## 最终 dcbc 冻结复验

静态自查发现保留合法 PURL 键时仍会接受 namespace dot 段；新增 pkg:generic/../../private、pkg:npm/%2e%2e/private 两条 unit 先得到2 failed，仅在 locator 字段的 PURL 特判拒绝 . / .. namespace 段，普通带 namespace 的 PURL 阳例仍保留。该补充没有改 snapshot/PURL reference 或 HTTP 判断。最终源码为dcbc3d92；9b22不是最终修复版本，早先红绿证据保留。

| 最终范围 | 真实结果（+08:00） |
|---|---|
| final_locator117 | 2026-10-16T09:11:14+08:00–2026-10-16T09:11:15+08:00，exit 0，117 passed，0 fail/error/skip |
| final_dcbc_regression616 | 2026-10-16T09:11:18+08:00–2026-10-16T09:12:40+08:00，exit 0，616 passed，0 fail/error/skip |
| final_default25_admitted | 2026-10-16T09:11:58+08:00–2026-10-16T09:12:09+08:00，exit 0，25 passed，0 fail/error/skip |
| final_history18_admitted | 2026-10-16T09:12:42+08:00–2026-10-16T09:12:56+08:00，exit 0，18 passed，0 fail/error/skip |
| final_inventory105_admitted | 2026-10-16T09:13:12+08:00–2026-10-16T09:13:48+08:00，exit 0，105 passed，0 fail/error/skip |
| final_migration119_admitted | 2026-10-16T09:13:58+08:00–2026-10-16T09:15:32+08:00，exit 0，119 passed，0 fail/error/skip |

最终117包含新增58和旧33/26，616范围包含旧59，彼此不能累加。PG25/18/105/119分组不重复累加为正式评分结果；默认入口与0019/0020→0021/0022、历史、事务、并发、故障回滚和原始raw/hash分别保留完整assert。没有执行downgrade。旧HEAD0019硬编码oracle的独审原红仍由root按合同演进追踪，本轮不修改、不skip、不把它算passed。
