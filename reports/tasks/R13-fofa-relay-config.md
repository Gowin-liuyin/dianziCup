# R13 / T08 / T25 · 第三方 FOFA relay 配置准备

状态：`awaiting_review`；本独立准备包实现 `complete`，整 R13/T25/T42 仍未完成。作者不登记 accepted。记录时间：2026-10-15T23:58:49+08:00（Asia/Shanghai）；各执行秒级时间以 run receipts 为准。

工作树 `D:/wt/r13-fofa-relay-config`，分支 `codex/r13-fofa-relay-config`；固定基线 `1a52e17ffe327fb8a0c1d4f97372948a699910e3`。业务代码冻结 `35a91e2644075238825724c2f3d7bbab83f30cde`。主仓未提交修改未接触；本包不 push、不改公共状态。

## 范围和文件

已读取真实 AGENTS、00 执行图、11/12 恢复合同的 R08/R13、03/05 数据与 API 合同、04/07、T08/T25/T27、任务状态和交接，以及最新 ponytail full。T25 原 C01–C06 及 R13 原资产要求保持，不能由本准备包签整卡。

仅五个业务/测试/示例文件：

- `backend/src/ai_intel/assets/fofa_relay.py`
- `backend/tests/unit/test_r13_fofa_relay.py`
- `backend/tests/contract/test_r13_fofa_relay_account_wire.py`
- `backend/tests/security/test_r13_fofa_relay_boundaries.py`
- `config/providers/fofa_relay.example.md`

另有本报告与 `reports/runs/recovery_r13_fofa_relay_config_20261015/` 自有证据。最终文件字节哈希见该 run 的 `artifact_manifest.json`。未改 settings、runtime、API、schema、迁移、依赖锁、金标、阈值、分母、进度或集成文档。

基线 rg 未发现 FOFA connector 或 assets 模块。复用既有 NetworkGateway、NetworkPolicy、OriginCredentials；固定 HTTPS origin、固定路径、10 秒/64 KiB、并发 1、重定向 0、单次不重试。秘密由可信进程环境注入；环境载入拒绝官方 provider、其他基址和不合页面格式的 key，repr 不显示秘密。fixture 注入须同时显式开启 fixture_mode，结果携带 is_synthetic。

## 文档及账户证据

文档页读取合计 8/8：检索工具对三个指定 URL 各失败一次；既有受控网关对三页各无鉴权 GET 一次；独立 IAB 打开飞书及 fafa 两页。浏览器页内 DOM/脚本观察不另导航、不资产搜索。未绕过证书、人机校验、重定向边界或发送消息。

首个 fafa 文档 GET 后证据脚本因 Windows GBK 无法打印 emoji 退出 1，正文未落盘；只记录已读事实，不伪造 hash/时间。其余网关文档 GET 在 23:42:19–23:42:23 执行：hamal 200、161623 字节、SHA256 `f9b669da4c49b93027b09fa2f6b41dac6662e6be596c0819e2dea5330457fe47`；飞书被网络策略拒绝，未放宽策略，后以正常 IAB 可读。`document_gateway_reads.json` 仅保留元数据，未永久保存网站全文或示例资产细节。

材料来源为 [用户指定 relay 页面](https://fafaapi.info/fofa.html)、[备用网页](https://hamal.cc.cd/fofa.html) 与 [飞书说明](https://xcnh3lhvc740.feishu.cn/wiki/CkdiwxYP6ifQaukDalvceLJknOh)，均为第三方资料。网页声明上游为 FOFA，不能据此称官方账户或官方直连已实测。

| 核对事项 | 实际证据及限制 |
|---|---|
| provider | 固定 `fofa_relay` / `third_party_relay`，与官方直连隔离 |
| 已确认 API 基址 | 飞书脚本示例为 `https://fafaapi.info`；未证实 hamal API 等价，不列凭据目标 |
| 搜索声明 | 飞书展示 GET `/api/v1/search/all`、query 参数 `key/qbase64/size`；本包未实现/调用搜索 |
| 只读账户路径 | fafa 已加载页面的 `validateKey` 使用 GET `/fofaapi/v1/validate-key`，只带 key，不带资产条件 |
| 账户字段 | 页面使用 valid、firstUsedAt、expireTime、todayRemaining、totalRemaining；失败显示 errmsg，本包不传出 errmsg |
| 邮箱 | 搜索示例及只读验证不使用邮箱；未发送用户邮箱 |
| 字段限制 | 飞书明确将返回 `product.version` 列为不支持，不能据产品名确认版本或漏洞 |
| 合同矛盾 | 飞书末段全字段声明与前面的不支持字段清单不一致；按严格可确认能力保留不支持，不补猜搜索 schema |
| 配额/费用 | 文档为约每日 200 次的声明，非成本合同；账户只读实测每日数字 200，字符串总额度不解释含义；费用 unknown |
| TLS | 第三方示例关闭 TLS 校验与 AGENTS 安全边界冲突，本包保持 CA/hostname 验证 |

真实鉴权探测 2/2 次，仅上述同一只读账户路径：

1. 23:49:16–23:49:17，候选适配器返回 `invalid_response`；命令退出 0 表示安全 receipt 脚本完成，账户验证未通过。原始响应未保存。见 `account_probe_receipt.json`。
2. 主控明确批准最后一次诊断，23:51:34–23:51:36；HTTP 200、application/json、132 字节，响应 SHA256 `13b123674f4945f20be7349f8ae2bc3e2f8b5c6ee931a79b468527ec3afc5a77`。安全结构记录 valid=bool true，todayRemaining=int 200，totalRemaining=str；日期仅类型，未保存值。见 `account_diagnostic_receipt.json`。请求 URL、key、账号标识、错误原文、响应正文均不落盘。

首次错误的原因由最后一次新响应定位为额度类型合同过严，不能称第一次响应重放。已将有界字符串总额度映射为 unknown，完全不猜它是否无限或数字；已知 0 则 budget_exhausted，数字正额度且两字段齐全才 available。额度缺失/空值与 error/valid false 不混用。鉴权失败、支付要求、限流、超时、非 JSON、供应商错误分别使用固定安全代码，不从错误文字猜额度。

修改后合同测试使用明确合成值；第二次正文没有保留，所以不能声称冻结适配器又实时解析同一正文。账户只读接口与凭据有效已由第二次真实响应证明；新解析仅合同测试通过，不再发第三次请求。账户可读不证明授权资产观察、正式 FOFA 权限、搜索字段或产品链路。

## 真实检查

完整 argv、工作目录、起止秒、退出码、日志字节哈希在 `check_commands.json`。Python 为仓外独立 venv，`uv sync --frozen --group dev` 退出 0，未新增依赖或锁文件。定向套件使用 `--no-cov` 仅避免无关全包覆盖率；随后运行原默认 60% 覆盖率门，无门槛变动。

| 类别/命令概要 | 结果 | 日志 |
|---|---|---|
| unit：pytest 新 unit --no-cov -q | 38 passed，exit 0 | unit.log |
| contract：pytest 新 account_wire --no-cov -q | 13 passed，exit 0 | contract.log |
| security：pytest 新 boundaries --no-cov -q | 12 passed，exit 0 | security.log |
| 既有 R03/T08 网络回归六文件 | 138 passed，exit 0 | network_regressions.log |
| Ruff check / format --check | exit 0 / 0 | ruff.log / format.log |
| mypy 新适配器 | 1 source file 无问题，exit 0 | mypy.log |
| 原默认 tests/unit -q | 1446 passed，1 warning，69.56% coverage，exit 0 | default_unit_gate.log |
| integration | not_run；无 PG、真实 HTTP 服务接线 | — |
| frontend | not_run；无 UI 改动 | — |
| e2e | not_run；无产品链路 | — |
| live | 账户只读真实证据如上；冻结解析未重新 live；资产 blocked_scope | 两账户 receipt |
| manual | not_run；未作人工资产核验 | — |

首轮红测试为模块尚不存在，pytest collection exit 2；模块添加后遇同名测试模块 collection 2，已通过独立文件名修复。初始 Ruff 2 项、mypy 2 项真实失败，保留 initial 日志；未禁用检查。

增加 64 KiB 大输入边界时，pytest 自动 fixture ID 超过 Windows 环境变量 32767 字符上限，产生 setup/teardown 2 errors；已改明确短 ID，输入与断言不变。首轮默认 unit 为 1444 passed/3 errors，另 1 error 为既有 R20 python-gil-held 子进程测试的超时，保留 `default_gate_before_short_fixture_ids.log`；本包不修改该测试或 CPU 实现。最终正常重跑通过，不能称既有间歇超时被本包修复。

CBM 官方 CLI 0.11.0 对本工作树 backend/src 建独立索引（1250 nodes/6244 edges），schema、gateway 调用方、OriginCredentials 调用方已 trace 并以 rg 源码交叉。CLI 默认排除名为 assets 的目录，即使文件 staged；不能将它冒充全覆盖。另以 assets 为根建专用模块索引，probe_account trace 7 callees/0 callers。源码 rg 也确认其仅为候选，公共 settings/runtime/API 无调用方。CBM JSON、两次索引限制与失败 trace 均保留。

## 边界、评分与下一步

资产搜索 0、扫描 0、模型调用 0，鉴权仅 2 次，付费结果费用 unknown。秘密仅读取主控指定单一 DPAPI 值，临时注入子进程环境并 finally 恢复/释放；不读其他 vault。仓外 venv/秘密不进前端、源码、索引或提交。`secret_scan.json` 是该单一真实凭据对自有产物的字节比对，只输出匹配数；合成测试 key 显式标记。没有资产明细进入普通报告、LLM、日志或未经授权持久区。

PG 事实权威不变，本包不保存资产、任务真相或历史快照。E1 本包仅贡献凭据目标约束、网络边界、脱敏和错误分类证据；F2/P2 仅供应商准备，不签资产定位/漏洞确认，也不与 R08 Hunter/Quake 聚合能力互换。

公共配置无需本包擅改 settings；主控可在评审后选择本独立环境载入入口，先显式选择 relay provider、仓外注入秘密、保持固定 origin。资产链路后续仍需 R11 权限/资产集合、费用上限、完整搜索响应/分页/观测时间合同、服务端限制查询、PG 不可变 snapshot/outbox、API/UI 和授权资产 live，不能凭本包继续泛域名搜索。

下一步：新非作者 reviewer 审冻结代码与证据；主控唯一登记状态并集成。保留首轮失败和外部限制，整 R13/T25/T42、T27 条件判断及正式 live 未完成。
