# G-D / R13 · 第三方 FOFA relay 配置与隔离修复独立审查

What this change does: 该候选配置只允许第三方 relay 的固定 HTTPS 来源和只读账户验证，区分额度未知、已耗尽及各类安全错误。本次修复使用显式 `None` 分支保留注入替身，避免合法 falsey 对象进入真实网关工厂。组件结论为 **Ship**；未发现新增可复现的 must fix / should fix 问题。

审查人为未参与上述业务与修复实现的新独立 reviewer。任务编号为 R13-fofa-relay-config / fix1；作者状态继续为 `awaiting_review`，公共 R13/T25/T42 状态及整卡/阶段验收未登记。记录时间：2026-10-16T00:42:01+08:00；实际执行秒级时间以本 run 收据为准。新工作区为 `D:/wt/r13-fofa-relay-review-fix1`，分支 `codex/r13-fofa-relay-review-fix1`；只新增本报告及 `reports/runs/recovery_r13_fofa_relay_review_fix1_20261016/` 的审查脚本、日志、XML、JSON 和局部字节保存属性。业务、原合同、主仓未提交修改及旧审查 raw 均未修改，无 push、无 accepted。

固定依据：基线 `1a52e17ffe327fb8a0c1d4f97372948a699910e3`；原业务 `35a91e2644075238825724c2f3d7bbab83f30cde`；修复业务 `2e1f5029a8e153bdd8289ac20b67e50d51e30bca`；完整审查 HEAD `9dfefa47183757aec0414cf701f4d4698827ff78`。已核对 AGENTS、执行图、R13、T25/T42、05 API/工具及 06 测试合同、03/04 资产证据和工具边界、07 资源及 CR-R06、相关任务状态/交接、两份作者报告与原初审失败日志；采用 Ponytail 5.2 review。预期负载是一个受控进程内单次账户请求：每客户端网关并发 1、10 秒总截止、64 KiB 响应、重定向 0；未据此评估平台多租户吞吐或完整预算执行。

## 行为和原 P1 复核

原初审 `test_independent_relay_boundaries.py:148` 实际失败：显式 fixture 模式下，`__bool__() -> False` 的替身通过配对检查，旧 `fixture_gateway or create_network_gateway(...)` 仍调用真实工厂，可能把真实请求结果标成 synthetic。原日志保留 **1 failed / 14 passed**，没有被新绿日志替换。

固定代码 [fofa_relay.py:175](D:/wt/r13-fofa-relay-review-fix1/backend/src/ai_intel/assets/fofa_relay.py:175) 校验 flag 与对象配对，:178 直接按是否为 `None` 选择同一个对象；:181–191 保留原非 fixture 网关策略。新增作者回归 [test_r13_fofa_relay_account_wire.py:53](D:/wt/r13-fofa-relay-review-fix1/backend/tests/contract/test_r13_fofa_relay_account_wire.py:53) 以调用即失败的真实工厂 Mock 检查零调用、唯一固定请求、额度与 synthetic。独立复跑原整份 15 例已全绿；额外 18 例检查 truthy、`__len__() == 0`、禁止评估 `__bool__` 的注入对象均保持身份并零调用真实工厂。因此原 P1 已关闭，最小修复为现有显式分支，无需新增包装层、依赖或配置。

完整组件复核并非只检查该分支：

- 配置 :65–89 拒绝官方 provider、其他基址及不合格式的合成 key；缺 provider/key 返回 `not_configured`，配置 repr 不带 key。
- 解析 :116–158 严格区分 bool/int/str。`valid=false` 为鉴权失败，供应商 error 不被成功标志覆盖；缺额、null、`totalRemaining=-1` 和有界字符串总额度保持 unknown，已知零额度才耗尽。重复字段、非有限值、异常类型、非 JSON、非法编码与超 64 KiB 均拒绝，不从错误文字猜额度。日期、资产字段被丢弃，不把 retrieved_at 当 observed_at。
- 请求 :193–214 只有固定账户路径，无搜索入口、邮箱或调用方自由 URL。真实策略通过本地传输复跑：只在准确 origin 注入 key，URL/反射 header 脱敏；私网、环回、链路本地、IPv6 私网及公私混合 DNS 在运输前拒绝；响应大小、HTML、重定向、DNS/流式超时、HTTP 401/403/402/429/5xx 分类均检查。可重试标志只表达错误性质，客户端不执行重试，异常链打印不泄漏合成 key。

## 实际命令与分层结果

Python 为既有仓外 `D:/dianzi-runtime-cache/r13-fofa-relay-config/venv/Scripts/python.exe`，版本 3.12.13；未安装依赖。每条命令通过本 run `run_command.py` 留存完整 argv、cwd、真实上海起止秒、HEAD、exit、输出字节长度/SHA256。显式 `PYTHONPATH` 指向本 WT/backend/src，import_origin 已验证实际导入此固定候选。子进程移除 TEST_/DIANZI_ 和 API_KEY 环境变量；未读取 DPAPI/vault 或凭据值。

下列 pytest 的完整共同后缀为 `--no-cov -q -p no:cacheprovider --junitxml <本run对应XML>`；cwd 为本 WT/backend，完整命令可见相同 label 的 JSON 或 `check_commands.json`。定向 `--no-cov` 不修改仓库原 60% 门槛；本轮未跑全仓默认门。

| label / `python -m pytest` 后的路径 | 真实时间 +08:00 | 结果 / exit |
|---|---|---|
| suites：tests/unit/test_r13_fofa_relay.py、tests/contract/test_r13_fofa_relay_account_wire.py、tests/security/test_r13_fofa_relay_boundaries.py | 00:36:28–00:36:29 | 38 unit + 14 contract + 12 security = 64 passed / 0 |
| network_regressions：tests/unit/test_r03_network_gateway.py、test_r03_network_review_regressions.py、test_r03_doh_resolver.py；tests/security/test_t08_network_and_sources.py、test_r03_network_transport.py；tests/contract/test_t08_network_redirects.py | 00:37:22–00:37:25 | 138 passed / 0 |
| previous_independent_boundaries：D:/wt/r13-fofa-relay-review-1/reports/runs/recovery_r13_fofa_relay_review_1_20261016/test_independent_relay_boundaries.py | 00:37:26–00:37:27 | 15 passed / 0；旧原文件只读 |
| independent_boundaries：本 run/test_independent_relay_fix1.py | 00:37:27–00:37:28 | 18 passed / 0 |

合计 **235 个不同用例，0 failures、0 errors、0 skipped**，XML逐项可复算；不把作者重跑计入本次总数。unit/contract/security 为 `passed`，安全检查全使用本地合成数据与传输，不计真实前后端 e2e。

静态 cwd 同为 backend：`python -m ruff check` 和 `python -m ruff format --check` 均覆盖产品文件及原三类测试四文件，00:37:28–00:37:29，exit 0/0；`python -m mypy src/ai_intel/assets/fofa_relay.py` 00:37:29–00:37:31，exit 0，1 source file 无问题。业务 `git diff --check` exit 0；从 2e1f 到 HEAD 的 backend/config diff exit 0 且为空。保护路径对基线 diff exit 0 且为空，包含 AGENTS、docs/contracts/progress、网络实现、API、迁移、依赖与前端。日志中没有掩盖业务失败或改 skip。

## 索引、真实调用链与证据字节

CBM 官方 CLI 0.11.0 在独立缓存 `/tmp/dianzi-cbm-r13-relay-review-fix1-20261016`、persistence=false 上索引本 WT。src-root 1250 nodes / 6244 edges 明确排除 `ai_intel/assets`；另建 assets-root 37 / 84，not_indexed/partial/unusable 均 0，未索引秘密、报告、测试或 holdout。两根均实际执行 get_graph_schema。五个 trace 均使用真实 qualified name，而非只列工具计划：

| 图根与函数 | 实际 trace 结果 | 源码交叉与限制 |
|---|---|---|
| src / ai_intel.infrastructure.network.create_network_gateway | 1 callees / 6 callers | → NetworkGateway；rg 另发现 assets :181，因为默认图排除了 assets |
| src / ai_intel.infrastructure.network.OriginCredentials.inject | 2 / 5 | ← _fetch → _bounded_fetch → fetch/post_json；准确 origin 约束见 network.py:338 |
| src / ai_intel.infrastructure.network.NetworkGateway.fetch | 24 / 1 | → _bounded_fetch/_fetch → 地址校验、deadline、response.close、脱敏；相关行为由本地传输与138回归验证 |
| assets / fofa_relay.FofaRelayClient.__init__ | 1 / 0 | 窄根缺导入依赖，源码 :181/:189 与公共图交叉，不能据图声称未调用网关 |
| assets / fofa_relay.FofaRelayClient.probe_account | 6 / 0 | → parse_relay_account_response/_quota_value；Protocol fetch 动态分派需源码/实际测试补足 |

rg_relay_callers 在 backend/src/backend/tests/config 中确认：产品代码仅本模块声明，没有 settings/runtime/API 的生产调用方；直接调用仅 contract/security 测试。原报告中的历史受控账户脚本属于历史证据，本次没有执行。图中 0 callers 本身不证明全仓未接线，结论还以 rg 和读取源码交叉支撑。未接 PG/API/UI/search 是组件范围，不能称完整 FOFA 已可用。

作者 fix1 manifest 的 Git 原字节 SHA256 为 `0ef8cb1d3c685096ca0edd760830dd397603cc7308f7ba250092d41564409b96`，62 项全部按 Git blob 校核通过。原配置 manifest SHA256 为 `aba0fba2f6150eb385e05a83869a5245d55a582dda8ae2ff60426bd81a73cf88`，47 项按其原业务 SHA 与保留证据 blob 校核通过。checkout 中 CRLF 可与 blob 不同，本次没有归一化、回写或裁剪原 raw。

审查工具的首次 author_artifact_verification exit 1：误把历史 manifest 的两个已修复业务文件与当前 HEAD 比较；这是审查脚本版本选择错误，并非业务或作者制品失败。原脚本保存为 verify_evidence_initial.py，失败日志保留；更正为每份 manifest.code_sha 后，于 00:38:02–00:38:08 exit 0。原审查 test/log/XML 在末次封存时再按先前记录的 SHA256 校验不变。新 run 的 artifact_manifest.json 封存本报告及自有脚本、原日志与收据，避免自递归；没有以该清单修改原清单。

## Live 限制、原验收与交接

本轮 live、integration、frontend、e2e、manual 均 `not_run`；未跑 PG、HTTP 服务接线、全仓 unit/CPU 门、性能、连续运行或模型评测。新增鉴权/文档读取/资产搜索/扫描/模型调用/秘密读取均 **0**。原两次鉴权 2/2 已用尽，未发第三次请求。

历史安全 receipt 只记录 2026-10-15T23:51:34–23:51:36 的真实 HTTP 200、JSON 132 字节、valid=bool true、todayRemaining=int 200、totalRemaining=str。响应正文未留存；冻结适配器与新字符串兼容解析只有合成合同测试证据，不能声称此次再次 live 或重放原响应。费用 unknown，不能从日额度推成本。它仅证明当时第三方 relay 的账户只读响应及凭据有效，不能证明官方 FOFA 账户、搜索字段、资产授权或资产观察能力。

R13 原要求为认证上下文内授权集合的被动观察、范围拒绝、空结果语义、缺观察时间、余额/权限/超时、新快照与重判。当前包只贡献账户与网关准备。T25-C01—C05 的完整资产行为均未验证；C06 只有配置/账户额度/错误子项通过，搜索字段 partial 尚未实现。T42-C01—C06 无页面/快照/研判/导出执行证据。授权资产 live 仍 blocked_scope；缺费用上限、搜索响应/分页/观察时间合同、R11 权限集合、PG snapshot/outbox 与 API/UI 集成，不能签整 R13、T25、T42 或 G-D。

无公共合同/依赖/金标/阈值/计分分母偏差。E1 证据限于准确凭据目标、脱敏、单次预算边界、错误分类与合法 fixture 隔离；F2/P2 不取得资产定位或漏洞确认通过结论。下一步建议主控仅登记与集成该候选组件；资产观察继续按原 R13 范围取得最小授权/合同资源后另行实现和独立 review。

Verdict: Ship. 仅限固定版本的第三方 relay 配置与账户验证组件，以及 falsey fixture 隔离修复。

Not checked: 真实冻结解析、官方 FOFA/search、授权资产端到端、公共运行时/PG/API/UI、多租户预算执行、性能/连续运行及人工资产核验；整卡和阶段保持未完成。
