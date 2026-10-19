What this change does: The repair requires a pinned official ATLAS artifact URI and matching full commit identity before a model call. It also keeps explicit version conditions and their wrapped continuation text in the returned raw expression and quote.

**G-C / R07 model-fields 两根因定向复核：限定 Ship。首次审查的两项 Must 已关闭，未发现本修复范围内的新阻断。** 仅签本片候选代码，不签整 R07、原 T 卡、G-C 或产品/live；不写 accepted。

本次仍由原非作者 reviewer 独立复核，未 spawn。只新增本报告与 `reports/runs/recovery_r07_model_fields_review_1_recheck_20261016/`；未改业务源码、原测试、合同、配置、依赖、状态或原证据，未 commit/push。外网、真实模型、真实凭据、资产、PoC 执行、PG、worker/API/UI 本轮操作均为 0。

| 固定身份 | 值 |
|---|---|
| 修复代码 | `696b1d88045ee862db1af3aaf569574ad361feaf` |
| 修复完整材料 | `ef24758bd8e9e3e1e8e24760d330a9ffe62af341` |
| 首次材料基线 | `6199ad193d36da17c6597ee286aae40af887d425` |
| 修复 manifest 本体 SHA-256 | `1d57ce725de521581cd3798ead71f47d17975430ab42747d2f1afce9606e5943` |
| 新独立 worktree / branch | `D:/wt/r07-model-fields-review-1-recheck` / `codex/r07-model-fields-review-1-recheck` |
| 解释器 / import 根 | 既有 Python 3.12.13 `D:/dianzi/backend/.venv/Scripts/python.exe` / 当前 WT `backend/src` |
| 首条记录时刻 | `2026-10-16T01:40:51.472777+08:00`，实际 Asia/Shanghai |

复读 AGENTS、执行图、R07/R09 恢复卡、修复报告、固定 progress/handoff；沿用首次已读 T13/T20/T22/T23、03/04/05/06、candidate/v3 合同和 Ponytail 5.2 review 规则，并核对相关合同在本修复 diff 中无变化。作者 worktree 干净；审查在新 WT 上进行。固定旧 progress 中整 R07 pending 仍只是索引，不据此推断能力缺失或主控活动代码状态。完整材料与代码的 source/test diff 为空，review WT 的 source/test diff 也为空。

两项关闭依据：

1. **浮动 ATLAS taxonomy 门禁已关闭。** `field_sources.py:93–114` 的同一函数同时用于调用前门禁与候选验证。当前只识别 HTTPS 官方 `raw.githubusercontent.com/mitre/atlas-data/<40位commit>/dist/ATLAS.yaml` 或 `github.com/mitre/atlas-data/blob/<40位commit>/dist/ATLAS.yaml`；`source_version` 必须逐字等于 URI 内 commit，并保留 full_text / blocks_complete 前置。main/latest、伪固定 label、短 hash、错配 hash、非官方地址/路径、query/fragment/userinfo/异端口均不能开启 ATLAS 调用；模型输出改写版本也不能产生候选。原两条浮动版本负例已从红变绿，新增拒绝路径和两个正常固定形状均通过。

   限制符合本片候选合同：支持这两个明确的固定官方 artifact 形状，普通 MITRE 当前技术页、release label 或其他未支持形状安全保留 `pending/atlas_taxonomy_missing`，没有伪绿、默认版本或猜映射。40 位字串是输入结构绑定，不证明该 commit 实际存在或下载内容真实。合成 `a×40` 明确只在测试内使用；真实官方加载器仍须验证来源、下载和不可变版本。本轮不做真实加载，也不把格式检查称为真实性验证。扩展其他固定官方格式若后续需要，应由加载器和合同明确提供，不能凭模型自报放行。

2. **同块同段跨行必要条件丢失已关闭。** `field_sources.py:177–224` 从实际 quote 坐标找到所属段落，核对显式必要条件标记及换行续文在同一 `raw_expression` / 完整 quote 内。原 `range\nOnly when remote tools are enabled.` 仅引用范围一行的负例被拒绝。前置/后置条件、CRLF、关键词换行、续行、多条条件、中文显式条件、漏第二条件、把条件单放 limitation 或单独 quote 的路径都拒绝；完整原文保留为 pending model hypothesis，版本比较仍 unknown。正常单行条件、完整跨行表达式、已有标点和 quote 坐标/hash/边界回归通过，空行分段的独立内容保持原边界。

   本次只证明受支持的显式同块同段边界。跨块、跨段、隐含语义及未支持自然语言仍需语义/人工复核。同段无关显式条件可能导致保守拒绝，作者已明示；它不会变成无条件确定结论。版本数字紧邻句末句点的保守拒绝是首次旧正例仪器记录中的既有限制，本修复未修改该版本数字识别算法；不据本次通过宣称任意标点/自然语言都已覆盖。

实际自动执行结果：

| 检查 | child 退出码 / 数量 | 新 run 证据 |
|---|---|---|
| 原 reviewer 文件按字节复制后复跑 | 0；47 passed，0 fail/error/skip/warnings | `original_47.*` |
| 原指定回归 | 0；236 passed，0 fail/error/skip/warnings | `original_236.*` |
| 修复新增必要边界 | 0；46 passed，0 fail/error/skip/warnings | `new_46.*` |
| 新独立真实 gateway/transport 调用预算 | 0；32 passed，0 fail/error/skip/warnings | `gateway_independent_final.*` |
| Ruff / format / mypy | 各 0；六个相关 source/test 文件，mypy 两业务模块 | `ruff.*` / `format.*` / `mypy.*` |
| source/test 与本修复完整包 diff check | 各 0；基线 6199 → ef247 | `source_diff_check.*` / `package_diff_check.*` |
| 修复材料与原材料审计 | 0；新 103/103 Git blob 和作者 raw 精确 hash+size；源 3/3；旧 73/73 保全 | `evidence_audit.*` / `material_audit.json` |
| CBM src-only index/schema/qualified traces | 各 0；1326 nodes / 6623 edges，未索引/partial/unusable 0 | `cbm_index.*` / `cbm_schema.*` / 两 trace |
| 源码 `rg` 调用方核对 | 0；新 helper 入链，固定快照模型候选入口仍无产品调用方 | `rg_callers.*` |
| 固定身份和源码未改核对 | 各 0 | `identity.*` / `fixed_code_diff.*` / `no_source_mutations.*` |
| 限定文件模式扫描 | 0；81 文件 / 0 findings，原 scanner PATTERNS 未改 | `scope_scan.*` |

最终四组为 236 + 47 + 46 + 32 = **361 个通过检查**，不是准确率、召回或评分分母。236 仍是原 56 新 unit / 4 contract / 16 security + 160 相关既有检查，包含既有 R05 原 60 例。两个原 reviewer 文件 SHA 与首次最终文件逐字相同，未修改原失败断言，也未删用例或改 skip；旧作者保留的 `frozen_red.xml` 仍为 44 passed / 3 failed、exit 1，真实 red 时刻和 receipt 保留在原修复包。

本 reviewer 新 32 例的首次运行 28 passed / 4 failed，只因 reviewer 错填 503 预期错误码 `model_retryable_unavailable`。实际既有 `classify_http_failure` 合同为 `transient_server_error`，生成层输出 `model_transient_server_error`；修正 reviewer 预期后 32 例全部通过。初始仪器 `test_gateway_independent_initial.py.txt`、`gateway_independent.*` 的失败日志/JUnit/receipt 保留，没有改业务、原测试或预算断言。这四个仪器错误不被当成产品缺陷，也不被隐藏为 skip。

所有命令由 `run_recheck.py` 保存真实 argv、cwd、+08 起止、child exit、固定完整/代码/基线 SHA 与 PYTHONPATH。wrapper 记录失败后自身可能为 exit 0，上表使用 child receipt/JUnit。pytest 仍用 `-o addopts=` 做指定有界套件，原默认 `--cov-fail-under=60` 未改；没有 whole-project coverage 或整 pure/native-CPU 套件通过声明。

独立预算核验更低于作者的 transport stub：新 32 例实际运行 `GenerationClient.generate → NetworkGateway.post_json → _bounded_fetch → _fetch → PinnedHttpTransport.request → _HttpResponse`，只把 DNS resolver 与 `_PinnedConnection` 的 socket/HTTP 响应边界换成离线合成实现。没有替换 generate、post_json 或 transport.request 的业务逻辑；generate 的观察 wrapper 调用原实现并记录真实 `GenerationRequest.allow_format_repair=False`。

四 provider × 六路径（success、format、503、302、network、timeout）的每次尝试均在 `max_calls=2` 下观察到恰好四次 connection POST、四次 DNS resolver 调用和四条 AttemptMetadata。resolver 提供两个公开 IP，但真实 transport 只用第一个，无失败后换 IP。302 未产生第二请求；format 未修复重试；网络/超时/503 未重试。预算 7 的每次 wire 上限为 floor(7/4)=1，合计请求上限 4≤7；usage/fee 保留既有 unknown 语义。四 provider × 两拒绝路径的预算未授权/私有未获外发授权均为 0 DNS、0 POST、0 GenerationClient 调用。此处 wire 指离线边界观察；真实 socket、TLS、DNS、供应商和计费请求均为 0，仍不能算 live 或 integration。

代码检查确认修复只改来源层 shared gate / qualifier helper，生成/client/network/transport 公共代码未改；字段边界继续独立测试。文献身份仍由 context 内精确 URI 绑定，模型自填 target IDs/跨 revision 引文/partial 正文升级被拒绝；PoC 仍仅 candidate_found，拒绝 static_reviewed/lab_verified，未获取或执行仓库；合法输出仍 MODEL_HYPOTHESIS / PENDING，未成为 verified。引文存在仍不等于内容支持。

材料保全分列：

- 修复 manifest 本体 hash 与主控提供值完全一致。103 项在固定 Git blob 和作者 raw 中均精确匹配；新 review checkout 102/103 字节精确匹配，唯一 `.gitattributes` 发生普通 checkout CRLF 转换，固定 blob/作者 raw 仍精确一致，未改内容。三个修复 source/test blob 与 code696b 完全一致；作者 source 工作树 hash 与其清单一致。
- `.gitattributes` 新增规则仅为本次修复报告/run 的精确路径；raw log/XML 的 `-text/-diff` 用于原字节保留，未放宽业务源码或业务测试 whitespace。6199 → ef247 的 source 与新全包 diff check 都为 0；不把这个新修复范围结论冒称原 cb340 → 6199 的历史 raw whitespace exit 2 已被修改。
- 原 73 件材料作者 raw 73/73 精确匹配；固定 Git 原 blob 仍为 26/73 精确、73/73 仅换行归一内容一致，73/73 Git blob 与6199未变；原 manifest 字节也未变。旧红、draft 和材料失败证据未重写，没有用新 attributes 伪修历史字节。

CBM 使用官方 WSL `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`，独立缓存 `/tmp/dianzi-cbm-r07-model-fields-review-1-recheck-20261016`，只允许当前 WT/backend/src，persistence=false。真实 qualified 入口 trace 连到共享新门禁/helper、GenerationClient、网关和既有四维校验；入口 source callers 0 与 rg 一致。没有索引 reports、holdout、秘密、附件，也没有审查未冻结的 root publication/worker 活动代码。负载判断仍限单个受控事件尝试、最多四维串行与既有共享 client 并发槽，未声称生产吞吐。

| 恢复验证层 | 本次限定结果 |
|---|---|
| unit | passed：本片原/新边界与指定回归 |
| contract | passed：指定离线结构、codec、引文/候选契约 |
| security | passed：指定离线注入/身份/外发/PoC/预算边界；不签全系统安全 |
| integration | not_run：无 PG/worker/API，离线真实 transport 代码路径仍不是外部集成 |
| frontend | not_run |
| e2e | not_run |
| live | not_run：真实官方 immutable taxonomy 加载、供应商行为/费用仍未核验 |
| manual | not_run：无人工标注、真实样本裁决或最终评分验收 |

F2/P2 的本次证据是固定 taxonomy 输入边界、必要条件保留、未知比较与故障隔离；R1 仅沿用文献目标/partial 正文边界回归。完整九维、R09 知识卡、PG 发布/历史/重放、业务链 live、原六验收、阶段门和性能指标仍保留，不从本次候选 Ship 推定通过。后续最小输入是受信加载器提供真实固定官方 commit/内容，及新冻结的产品接线版本；由其独立审查验证发布/权限/语义，而非据此模型假设直接发布事实。

Verdict: Ship — only this repaired model-fields candidate slice.

Not checked: real taxonomy authenticity/loading, cross-block/cross-paragraph/implicit semantic conditions, production PG/worker/API/UI consumers, real provider traffic/fees/TLS, production throughput, human/scoring acceptance, whole R07/G-C.
