What this change does: 本批把 NVD 归一化改为真实 CVE API 2.0 字段，增加固定 vLLM 厂商公告适配器，并用 0013 保存修订来源时间、响应引用和文本定位。它提供来源组件与前向迁移；冻结版尚未接通来源 worker、事件 API 或页面链路。

审查结论：**G-B/R04 来源小批 needs_changes**。三个确证问题必须先修复；厂商适配器纯函数和 0013 旧数据保留可作限定通过意见。整 R04、原 T 卡及 G-A/G-B 均未签通过，未更新 progress、锁或业务代码，未提交、未 push。

首次创建/本次写作开始：2026-10-15T13:19:33+08:00；审查 Agent：/root/r04_sources_independent_review；审查结束以证据 manifest 的实际时间为准。早期命令未落盘的准确时刻不追补。本报告所有源码结论针对下述冻结 worktree，作者报告不是正确性证据。

## 冻结范围与依据

- 完整目标 SHA：`2ff2f999b3824252d54b93af6d1da78ecb6f1427`；tree：`5af8185a14984d61d6c4dab5cc85932ac7ed294c`。
- 实际 diff 基线：`2522b3a941030f373ccd1736bd54cee411e939a9`。来源作者提交 `0e622ced2f345cb6dbccab21707119f4e6836f74`；厂商作者提交 `40843942416f4baeb59379c0a1862c5d8a9e5c1e`，集成为上述目标。
- 独立分支：`codex/recovery-r04-sources-review-1`；worktree：`C:/Users/yinha/.codex/worktrees/recovery-r04-sources-review-1/dianzi`。创建后与检查结束 `git status --porcelain` 均空。主目录后续代码和 `5c62e69` 文档快照不计入业务审查。
- 审查源码及直接测试/留档 diff 共 15 文件、1165 增/91 删，见 [冻结 diff 与行号](D:/dianzi/reports/runs/recovery_r04_sources_review_1_20261015/frozen_diff_and_lines.log)。Ruff、format 和类型检查均针对冻结路径；共用已锁依赖的 Python 解释器，`PYTHONPATH` 明确指向冻结 `backend/src`，未安装或修改依赖。
- 已读 AGENTS、执行地图、11/12 中 R04 与阶段要求、T05/T09/T10/T12/T13/T14/T40、03/05 合同、当前状态与交接、CR-R04-R04_source_persistence、来源作者报告；厂商作者报告读取其 `acfea349f7e831f48c0a08a6e09ef69e261eb884` 封存 worktree。已实际读取新版 [ponytail-review SKILL.md](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)，按正确性、安全、并发与可复现证据审查。
- 没有读取用户产品凭据、KEYS、`.env` 或 holdout，没有执行 PoC、扫描、模型付费调用或重复外部来源 GET。官方 PDF 本轮未重读；本批不改变官方评分、来源类别、金标、分母或精度门槛。

## Must fix

1. **并发响应引用仍可丢失原文字节**（P1；[revisions.py:317](C:/Users/yinha/.codex/worktrees/recovery-r04-sources-review-1/dianzi/backend/src/ai_intel/knowledge/revisions.py:317)，物理删除在 332，PG DELETE 在 333）。
   - **职责与触发：**新增 `revision.source_response_hash` 和 `fetch_attempt.response_content_hash` 都必须保护完整 HTTP 原文。独立专用 PostgreSQL 中，回收完成四组 COUNT 后、进入 `ContentStorage.delete_object` 时，让第二线程的真实 Session 提交其中一种新引用；两种引用均实测成功提交。
   - **实际问题：**当前回收先删除字节，再执行 PG DELETE；后者因刚提交的外键引用而抛 `IntegrityError`，数据库事务回滚，原对象登记和引用仍在，但 `read_verified` 已抛 `FileNotFoundError`。现有 hash advisory lock 只会协调同样获取该锁的写方，新增列直接写入没有这个保证。PG 外键保护了行，未保护此前删除的文件。
   - **最小修复/复验：**删除顺序须先确认 PG 允许删除，再物理删除；来源写服务在存字节、登记及提交响应引用前，与回收共用同 hash 锁。用 savepoint 明确处理引用竞争，不能留下失败 Session 后返回假成功。重跑本报告的两种真实并发负例和原 T05/来源元数据回归；允许竞争写方明确被拒绝或阻塞，唯一不可接受的是已提交引用指向缺失字节。
   - **若跳过：**完整响应证据不可重读，JSON pointer 虽在库中也失去可核验原文。这里只证明组件直接 SQL 写引用与回收的竞争，未声称已有来源 worker 调用；没有扩展断言调用方后续主动 rollback 的其他场景。

2. **NVD 将未知或非法时间变成确定 UTC 时间**（P2；[nvd.py:74](C:/Users/yinha/.codex/worktrees/recovery-r04-sources-review-1/dianzi/backend/src/ai_intel/ingestion/sources/nvd.py:74)，解析在 82、归一化在 85）。
   - **职责与触发：**业务时间必须显式可信，无时区原值保持 raw，不能猜偏移。对 `published` 分别输入 `2026-10-15T04:00:00-00:00`、`...+00:60`、`...00.1234567Z`、`...+01:00:30`。
   - **实际问题：**分别输出 `04:00:00+00:00`、`03:00:00+00:00`、`04:00:00.123456+00:00`、`02:59:30+00:00`；未知偏移被当作 UTC，非法分钟被进位，精度被静默截断，非来源合同偏移也被接受。同批厂商适配器已拒绝未知偏移和损失精度，NVD 的 `datetime.fromisoformat` 宽松接受造成不一致。
   - **最小修复/复验：**在标准库解析前做来源格式校验，拒绝未知 `-00:00`、非法偏移和超出可无损存储的小数精度，合法 naive NVD 时间继续仅保留 raw/业务 None；不修改历史时间或默认为抓取时间。重跑四负例、合法 offset/microseconds 和现有 naive 样本。
   - **若跳过：**未来时效/时间查询拿到伪确定或损失精度的来源时间，违背未知不等于事实的合同。未据这些合成时间计算时效成绩。

3. **NVD 描述、CWE 与引用绕过 UTF-8/NUL 校验**（P2；[nvd.py:128](C:/Users/yinha/.codex/worktrees/recovery-r04-sources-review-1/dianzi/backend/src/ai_intel/ingestion/sources/nvd.py:128)、149、157–170）。
   - **职责与触发：**进入业务的外部文本要可严格编码并能存入 PostgreSQL；恶意引用不能绕过文本边界。分别将英文描述、weakness.description.value、reference.url 路径改为含 `\u0000` 或孤立 `\ud800` 的文本，共六个负例。
   - **实际问题：**六例均返回正常 `NvdRecord`，没有输入拒绝。描述与 CWE 直接取字符串，引用只做 `urlsplit` 的 scheme/host/user 检查；该操作不会验证这些文本的 UTF-8/NUL。模块自己的 `_optional_text` 已有校验，却未应用到这三个输出字段。
   - **最小修复/复验：**在保留原值前复用现有严格文本校验，并保留引用的 URL 校验；结构/编码错误应明确失败，不能删坏字符或变为“字段缺失”。重跑六负例及真实样本、混合 Unicode、缺字段/Rejected 和厂商恶意 URI 回归。
   - **若跳过：**归一化成功对象在后续编码或数据库写入时才失败，来源失败归类与复跑边界不准确。这里确证的是归一化边界缺陷，没有伪称本冻结版已经执行这些产品入库路径。

三组为 12 个实测业务失败，不拆成 12 个重复缺陷。无纯风格、猜测性性能或计划外扩展 finding。

## 实际检查与限定通过意见

| 检查 | 实际 +08 起止 | exit / 测试数 | 证据 |
|---|---|---|---|
| 真实留档 NVD/vendor + 原 T10/T12/T13 | 13:12:52–13:12:54 | 0；131 passed，0 error/fail/skip | `target_original_contract.command.json/.log/.xml` |
| 原纯 unit 门槛 | 13:12:52–13:13:21 | 0；396 passed，0 error/fail/skip，1 warning | `pure_unit.command.json/.log/.xml/.coverage.json` |
| 实际 PG metadata / R02 migration / T05 | 13:12:52–13:13:00 | 0；21 passed，0 error/fail/skip | `pg_source_migration_t05.command.json/.log/.xml` |
| 独立负例首轮 | 13:15:07–13:15:11 | 1；16 tests，13 fail/3 pass/0 error/skip | `independent_boundary_first.*` |
| 修正自建正例后的独立负例 | 13:16:38–13:16:40 | 1；16 tests，12 fail/4 pass/0 error/skip | `independent_boundary_final.*` |
| Ruff / format | 13:13:48–13:13:50 | 各 0；10 文件 | `ruff_changed.*` / `format_changed.*` |
| mypy | 13:13:51 | 0；65 source files | `mypy_all.*` |

上述均为本 reviewer 实际执行，不沿用作者 332/374。重复执行不能相加为独立测试数量。纯 unit 的原始 JSON 为 **2599/4127 = 62.97552701720378%**，missing 1528、excluded 42；使用原 60 门槛，没有以终端 `63%` 代替原始数，也没有改变计分分母。

完整 command/cwd/起止秒/exit/test count/版本在 [原始证据目录](D:/dianzi/reports/runs/recovery_r04_sources_review_1_20261015) 内各 `*.command.json`。Python 3.12.13；pytest 8.4.2；pytest-cov 6.3.0；Ruff 0.16.9；mypy 1.20.2；SQLAlchemy 2.1.1；psycopg 3.3.6；实际 PG 16.14。纯 unit warning 是已有 Starlette API deprecation；独立证据测试放在仓外，自行导入 T05 seed helper，因此有 `real_pg` 未注册 marker warning，未 skip 或修改任何 outcome。

首轮 13 fail 中有一项是 reviewer 自建正例误用了 `TextBlock.json_pointer`；冻结解析模型实际使用 `block_type='field:'+pointer`。修正后真实 NVD 正例通过，保留首次日志与脚本 `independent_boundaries_first_snapshot.py`，不把这一项计为业务错误。PG 并发测试也允许安全实现拒绝竞争引用，断言针对已提交引用的可重读性，不要求某一种锁或删除顺序。

留档真实正例仅属 unit/contract：NVD 原 wrapper、机构/向量/数值与 JSON pointer 可对应原文；自身补测 CVSS 2.0/3.0/3.1/4.0 并存。vendor 原 8800 字节 SHA-256 `f084ddcb1eecd43494ac0244dd3b650431727add18deb330bc3df1722912cedf` 与 provenance 一致；无 CVE、后补 CVE 仍同 GHSA/URI，受影响范围、修复范围和函数条件保留。它不判断范围内版本或 PoC 成功，也未验证 PG 事件主键稳定。

0013 实际前向升级保留旧 created_at、未知来源时间/URI/parser 为 NULL、parse_status 为 legacy_unverified、旧 Unicode 坐标和文本；新增 parse_status/page check 与两类响应 FK 生效。已提交、无竞争的两类完整响应引用防回收通过；并发回收仍失败。已有 T05 A→B→A/原文字节历史/租户边界均在 21 项回归中复跑，未对 root 或其他 reviewer 数据库升级、降级或清理。

## 实际路径、性能边界与能力前置

实际 CBM 0.11.0 CLI，未发现已注册的 CBM MCP 工具。先读取 help/schema，仅索引自己的 frozen `backend/src`，项目 `dianzi-r04-sources-review-1-2ff2f999`，缓存在仓外 `/tmp/dianzi-cbm-r04-sources-review-1-20261015`；842 nodes/3676 edges，not_indexed/skipped/partial/unusable 均 0。`cbm_*` 日志及命令记录保留原始输出。

NVD trace：normalize_nvd_page → normalize_nvd_record → metrics/时间/文本；vendor trace：normalize_vendor_advisory → vulnerabilities/文本/时间。回收 trace 对接 ContentStorage 和 hash lock；save_document_revision trace 显示文档锁、对象登记与版本服务。图中 cleanup 的一个 self-edge 是 heuristic 0.5，不视为真实业务调用。

CBM 无 caller 只作定位提示。随后 frozen rg 和入口源码交叉确认：两个来源归一化入口只有定义/测试；API `create_application` 只挂认证/health，worker `EXECUTION_HANDLERS` 只登记 `record_source_fetch_failure`，不导入这些来源归一化服务；新响应 hash 仅模型定义、回收判断及测试写入。[冻结 rg/入口读取](D:/dianzi/reports/runs/recovery_r04_sources_review_1_20261015/frozen_source_callers.log) 与 `cbm_entry_trace`、`cbm_worker_entry_trace` 共同留证。不能把测试函数调用、一次匿名 GET 或新增 schema 算作来源 → PG → UI 产品能力。

负例每例单文档、单响应对象、两个 PG Session；原样本仅 3106/8800 bytes。NVD 页上限 2000、vendor 包/函数分别 256，文本预算 1,000,000 UTF-8 bytes，正常实现是对实际字段线性遍历；本轮未测大库、吞吐、并发产品负载或全链响应时延。四组回收 COUNT 的必要性是保护四种引用；未取得足以证明其生产性能问题的数据，不据此另立性能 finding。

G-A 未通过时可安全独立推进的部分是：纯来源解析、留档输入边界、兼容的前向列迁移与隔离测试；它们不依赖缺失的 worker/source/API 装配。真实网络调度、游标/任务事务、事件去重、别名合并、证据写服务、浏览器与模型闭环仍依赖后续冻结版本和阶段检查，不能用本意见跨阶段。此边界符合 00/11/12 与已批准的恢复能力切片，未删原 R04/T 卡验收条件。

## 状态、证据与交接

- unit：原回归 passed，但独立 NVD 边界 failed；contract：限定留档/原 T10/T12/T13 passed；integration：顺序迁移/历史回归 passed，但真实并发回收 failed。因此本批不能总记为 passed。
- security：仅上述边界负例，整卡 not_run；frontend/e2e/live/manual、原 T09/T14/T40 全部验收本轮 not_run。没有依赖到期 MinIO，ContentStore+真实 PG 记 integration；留档 JSON 记 fixture/contract；模型调用 0，不取得或报告付费结果。
- F1/F2/E1/P1 有来源字段/原文历史/工程检查的限定证据；持续监测、时效、准确率、召回率、问答能力、完整演示均没有本轮评分结论。
- 审查仅新增此报告和 `reports/runs/recovery_r04_sources_review_1_20261015/**`。没有修改业务、合同、progress、锁、盲测或用户未提交文件。
- 自己专用 DB `test_dianzi_r04_sources_review_20261015`，实际由只读内存加载 WSL 0600 测试连接创建；每负例 schema 在 finally 删除。13:19:07–13:19:17 已验证无 active session 后释放该 DB，证据 `database_release.command.json`；未释放其他人数据库/服务。没有长期后台进程，干净 frozen worktree保留用于复核原版本。
- 原始失败、脚本、JUnit、coverage、命令日志与文件哈希均在 manifest；实际测试凭据 full/所有连续 8 字节片段扫描结果见 `credential_scan.json`，不含秘密值。早期 tooling 错误和主目录误读纠正明确记在 `tooling_notes.md`；最终结论只使用 frozen 复读/复跑。

下一步：主控在有界文件范围修复三个 Must fix，冻结新 SHA 后让原 reviewer 定向复跑原 12 负例、原样本/时间合法值和 T05/PG/纯 unit60 检查；随后再接来源写服务及 worker/API/UI，按原 R04 六项条件取得真实链路证据。本报告不批准未实施的修复方案。

Verdict: fix 1, 2 and 3 first.

Not checked: 产品来源任务/游标/PG事件身份/API/browser/model live 全链、MinIO、持续运行、大规模性能、正式评测与人工验收。
