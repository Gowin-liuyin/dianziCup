# R04 · 厂商真实公告适配器切片

文档首次创建时间：2026-10-15T13:05:51+08:00
本次写作开始时间：2026-10-15T13:05:51+08:00
本次写作结束时间：2026-10-15T13:05:52+08:00
最后更新时间：2026-10-15T13:07:54+08:00
本工作包最早已记录基线核对时间：2026-10-15T12:55:23+08:00
代码编写准确起止/时长：历史未记录；不以测试窗口冒充编写时长。
本报告证据截止时间：2026-10-15T13:07:54+08:00
实现 Agent：/root/r04_vendor_source；主控集成：/root。
状态：awaiting_review；实现状态：本适配器 complete，R04/T12 整卡仍 partial。
独立审查：尚未发生；主控将创建新 reviewer，不由实现者自签。
工作分支：codex/recovery-r04-vendor；基线：08c2ff0f8ebcb4e5a0cc3c32d390bdb9518898c0。
已测/冻结源码 SHA：40843942416f4baeb59379c0a1862c5d8a9e5c1e；tree：fdbd190925d4c8a3d00282602f3c830f961339bf。
已审代码 SHA：尚未独立审查；push：未执行，子 Agent 不 push。
验证状态：unit passed / contract passed（适配器留档样本与既有 T12/T13） / integration not_run / security not_run（边界负例仅计 unit） / frontend not_run / e2e not_run / live not_run / manual not_run。

## 1. 范围、输入输出与前置

G-B/R04 的厂商公告适配准备，映射 T12 的厂商字段切片，服务 F1/F2/D2/R1 后续真实链路。不验收 T12 技术博客或 R06 持续采集，也不替代 T14 学术来源。已读取 AGENTS、执行地图、R04、T10/T12/T14、数据合同、工作流合同、来源资源、当前状态和交接。主控授权在 R03 未整体通过时推进此独立解析准备：纯函数不依赖网关未关闭问题，不运行正式 live 验收。

输入为主控经匿名受控网关取得的一个公开仓库公告响应，及原生 JSON object 单公告。输出 VendorAdvisory，固定仓库 vllm-project/vllm；数据只描述来源声明，不判断资产受影响、不执行 PoC、不读任意 URL、不写另一套内存事实。

真实诊断来源：2026-10-15T12:35:58+08:00 至 12:36:00+08:00，HTTP 200，8800 bytes。原记录 [主控 receipt](../runs/recovery_r04_sources_20261015/vllm_vendor_first.receipt.json)。本工作包没有重新调用来源 API，该原始诊断不等于产品数据库/页面/live 验收。

## 2. 当前问题、实现与复用

原 repository.py 接受 record_type/fixed_identifier/title/related_product 等内部简化字段，真实 GitHub repository-advisory 响应提供 ghsa_id、summary、html_url、vulnerabilities；将旧函数直接喂真实样本不能形成完整来源记录。CBM 与 rg 一致显示旧归一函数当前只被合同测试调用，没有产品入口。旧模块保持兼容，不平行重写仓库连接器。

新增 vendor_advisories.py 的职责仅为这一固定来源边界。复用现有 sources 模块布局、冻结 dataclass、类型/异常约定；复用标准库 re/datetime/dataclasses，不新增依赖、schema、迁移、锁文件或配置。固定来源精确 URI 比较拒绝用户信息、伪域名、改仓库、参数、片段、编码路径及非 HTTPS；描述中的不可信链接仍为文本，不抓取、不执行。

保留 GHSA 身份，CVE 可为空或后补；后补不会改变本对象 ghsa_id/canonical_uri，但 PG 事件主键稳定性尚未集成验证。包、生态、受影响范围、修复范围、函数条件分别保留；null/缺版本字段仍为 None，没有比较器或默认修复版本。撤回时间保留，不覆盖描述。

公开 state 必须 published；草稿/triage/closed 明确拒绝。时间必须显式已知时区，规范成 UTC；-00:00 未知偏移、无时区、无效日期和超 6 位小数时间明确失败，避免猜时区或损失精度。文本 UTF-8 严格校验并拒绝 NUL；最多 256 个包、每包 256 个函数、每函数 1000 字符、总输出文本 1,000,000 UTF-8 bytes；结构异常不转为空白成功。

外部未知字段仍由调用方保留完整 raw body；本适配器不宣称已归一 CVSS、credits 或正文所有风险条件。vulnerabilities 为显式空数组时输出空 tuple，表示没有已提供的包条件，不能推导“不受影响”；结构缺失/null 则失败。

## 3. 小接口冻结与文件所有权

主控派发输入输出冻结为 VendorAdvisory(ghsa_id,cve_id,title,description,published_at,updated_at,withdrawn_at,canonical_uri,product,vulnerabilities,source_schema_version='github-repository-advisory:1')。VendorVulnerability(package_ecosystem,package_name,affected_range,patched_version,vulnerable_functions=())。

主控在本工作包消息中明确批准增加 vulnerable_functions: tuple[str,...]，原因是官方响应有函数限定，不能丢条件。patched_version 已冻结名称保持兼容，docstring 明确它可能是来源修复范围而非单个确定版本。此项不改官方评分、金标、分母或版本判断算法，无新重大建设决策。

仅本 Agent 拥有并修改：

- backend/src/ai_intel/ingestion/sources/vendor_advisories.py
- backend/tests/unit/test_r04_vendor_advisories.py
- fixtures/recorded/vllm_vendor_20261015_public.json 与 .provenance.json
- reports/tasks/R04-vendor-adapter.md
- reports/runs/recovery_r04_vendor_adapter_20261015/**

工作区 C:/Users/yinha/.codex/worktrees/recovery-r04-vendor/dianzi，由 create_worktree 创建并已附本任务。未触及共享 checkout/用户修改、公共模型/迁移/配置/状态、API、runtime、阈值、盲测材料或秘密存储。无容器、数据库、后台服务和付费 API 资源需要释放；CLI 缓存在工作区外 /tmp/dianzi-cbm-r04-vendor-20261015。

## 4. 真实验证与失败记录

所有命令、工作目录、开始/结束、耗时、退出码在 run 目录 *.receipt.json；stdout/JUnit/coverage 原始结果保留。以下次数不能相加作为独立测试覆盖总数。

| 检查 | 时间（Asia/Shanghai） | 退出码/结果 | 原始证据 |
|---|---|---|---|
| 测试先行 | 12:58:54–12:58:56 | 2；1 collection error，模块尚未新增，预期红灯 | unit_red.log/xml/receipt |
| 第一轮适配器 | 13:00:00–13:00:02 | 0；76 passed | unit_first.log/xml/receipt |
| 最终 unit + 既有 T12/T13 | 13:01:26–13:01:28 | 0；91 新适配器 + 6 T12 + 6 T13 = 103 passed，0 fail/skip | unit_contract.log/xml/receipt |
| 纯 unit 原门槛 | 13:01:43–13:02:03 | 0；374 passed、0 fail/skip、1 warning；原始 62.138364779874216% = 2470/3975 ≥ 60 | pure_unit.log/xml/coverage.json/receipt |
| Ruff 首轮 | 13:00:50 | 1；测试 4 处超行长，未忽略规则 | ruff_first.log/receipt |
| format 修复后 Ruff/format | 13:01:26 | 各 0；4 文件 | ruff_final、format_final |
| mypy 冻结后 | 13:03:54–13:03:55 | 0；65 source files | mypy_frozen.log/receipt |
| index 字节与 stage 边界 | 13:02:47 | 0；4 文件、记录样本 raw SHA256 一致、通用秘密模式 0；实际秘密存储扫描未运行，由主控集成时执行 | source_freeze_check.json/receipt |

单元 warning 为既有 StarletteDeprecationWarning：httpx/TestClient API 将变化；没有改锁文件或添加 httpx2，记录为依赖维护提醒，不影响本切片测试结果。纯 unit 覆盖率直接读取 coverage JSON，没有利用终端四舍五入过门，未改变原 60 阈值或分母。

本轮没有业务测试失败。工具失败另记，不能冒充系统问题：runner 的 --cwd 初次放在 positional REMAINDER 后被 argparse 拒绝；get_graph_schema 初次缺 project（exit 1）后按真实 schema 修正；读取不存在 vendor_blog.py 的非终止 PowerShell 错误；未引用 HEAD^{tree} 在 PowerShell 导致 git 参数错误，之后引用同参数取得上述真实 tree。前三项中未有落盘时刻的写“历史未记录”，不根据文件 mtime补时间。CBM 缺 project 错误原日志保留，其余文本记录见 tooling_notes.md。

## 5. 代码图与真实接线

CLI codebase-memory-mcp 0.11.0。业务修改前索引范围 backend/src，项目 dianzi-r04-vendor-08c2ff0，819 nodes/3616 edges；全部成功解析，没有索引秘密/holdout/用户附件。schema 与 architecture 已取得。旧 normalize_repository_record graph callers=0；源码/rg 补核旧 T13 合同测试调用，不把“图无边”当作运行证明。

源码冻结后刷新独立项目 dianzi-r04-vendor-frozen 对应上述 SHA/tree；index 与 trace 日志在 cbm_index_frozen、cbm_trace_frozen。rg 冻结查找在 callers_frozen.log，只有定义与测试。本模块 **尚无 API/worker 产品调用方**，这是交付给主控的接线缺口；不能称已实时接通。

## 6. 来源依据与证据分层

[GitHub 官方 repository advisories REST 文档](https://docs.github.com/en/rest/security-advisories/repository-advisories)说明此 GET 返回仓库公告，公开资源可匿名访问，state 与分页由 endpoint 提供。官方响应字段是 patched_versions/vulnerable_functions，本切片保留原文。端点当前文档示例 API 版本 2026-03-10；真实诊断未显式传版本，本报告不把该请求冒称带此 header。

[GitHub 官方 GHSA 说明](https://docs.github.com/en/code-security/concepts/vulnerability-reporting-and-management/github-advisory-database)规定标识字符集 23456789cfghjmpqrvwx 和小写分段，校验按此实现，拒绝官方 REST 展示用的非实际合规 ID 示例。

样本来自 public vendor advisory，主要类别 vendor_advisory，不能同时用同条样本证明 code_repository 第二类覆盖。fixture/provenance 明确 is_synthetic=false 的留档响应，仅 unit/contract；没有当金标、不是浏览器模拟在线数据。记录 SHA256 f084ddcb1eecd43494ac0244dd3b650431727add18deb330bc3df1722912cedf，8800 字节，未重新序列化样本。首次实际公开来源发现来自主控网关；本切片自身请求数 0、模型调用 0，费用未取得写 unknown。

## 7. 未验证范围、复现与下一步

数据库/原文存储/证据坐标/源游标/任务原子性/分页增量/修订撤回传播/事件别名合并/API/前端/e2e/live/manual 全部未由本工作包运行。integration/security/frontend/e2e/live/manual 不算 passed；R04/T12/G-B 不过门。未实现任意仓库支持或通用 CRUD 框架，当前固定仓库是实际授权边界；扩源需冻结新配置/来源身份，不能放宽本纯函数为任意 URL 输入。

主控下一步把该纯函数接入共享受控网关、PG 原文/事实服务与已有读 API，保存原始响应和 evidence pointer，并通过真实 no-CVE→后补 CVE 以及修订/撤回链路验证后才进入 R04 独立整链审查。新的独立 reviewer 应复跑新 91 tests、T12/T13、pure unit 60，并检查固定入口、安全/缺时间/保留条件；实现者不签 accepted。

本工作区复现（不含任何真实秘密）先使用锁定后端环境并将 PYTHONPATH 指向 backend/src：

```text
python -m pytest tests/unit/test_r04_vendor_advisories.py tests/contract/test_t12_vendor_blog_connectors.py tests/contract/test_t13_community_repository_connectors.py --no-cov -q
python -m pytest tests/unit -q --cov-report=json:coverage.json
python -m ruff check src/ai_intel/ingestion/sources/vendor_advisories.py tests/unit/test_r04_vendor_advisories.py
python -m mypy src/ai_intel
```

本次实际 Python 为 3.12.13，使用 D:/dianzi/backend/.venv/Scripts/python.exe 的已锁依赖，PYTHONPATH 明确指向独立 worktree。原始命令完整绝对路径以 receipt 为准，不运行有硬编码 DSN 的 integration。

## 8. 文档修订记录

- 2026-10-15T13:05:51+08:00：首次根据当前源码、真实日志、实际系统时钟创建；历史未知不补造。
- 2026-10-15T13:05:52+08:00：写作完成，本切片 awaiting_review；无新验收或阶段 push 声明。

- 2026-10-15T13:07:54+08:00：封存检查源码 diff --check 为 0；证据 staged diff --check 为 1，仅 4 份 CBM 原始输出的末尾空行，原始日志保留不删改。主控已将源码4084394集成为2ff2f99并报告实际秘密扫描0；整链仍未验收。evidence_index 同时登记原始工作文件与 Git index 字节hash，明确换行过滤差异。
