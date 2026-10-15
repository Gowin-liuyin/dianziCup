# G-A / R03 网络切片独立审查 1

本改动做了什么：新增真实固定 IP 的 HTTP 传输，统一处理 DNS、CA、Host/SNI、逐跳重定向、读取上限和截止时间；另增加显式 Cloudflare DoH，默认仍为 system。本报告只审查此冻结网络候选，不审查另一 checkout 的后续 R04/PDF 或执行器实现。

结论：**needs_changes；修复问题 1–5 后再冻结并定向复核。** 独立原有回归 251 项及静态检查通过，但新增边界探针确证失败，不能凭当前一次 NVD 200 放行网络切片，更不能将 R03、T08 整卡或 G-A 记为 accepted。

## 冻结对象与独立性

- 基线：`0b983349e0468a4c75a1adf9f050ac3e7dd00686`。
- 目标：`f0e0b19df2813339138c5f727b4051eb794f9f78`。
- 目标 tree：`e975c28d331a7566f5bad0b82db7d157f7518754`。
- 独立分支：`codex/recovery-r03-network-review`；worktree：`C:/Users/yinha/.codex/worktrees/recovery-r03-network-review/dianzi`。从目标提交新建，开始时 clean；最终只有审查者的两个独立探针是未跟踪文件，业务代码、合同、schema、依赖锁和 progress 均未改动，未提交、未 push。
- 审查日志时间均为 `+08:00`；Git reflog 记录独立分支创建为 `2026-10-15T12:08:26+08:00`；锁定安装收据始于 `12:09:19.9629266`；独立负例执行为 `12:14:39–12:14:40`；独立公开 NVD 取样为 `12:16:02–12:16:03`。最终记录时间和文件摘要见运行目录 `manifest.json`，不填未记录的准备阶段起止时间。
- 已读项目 AGENTS、执行地图、R03 卡、T08 卡及其引用合同、固定候选的状态/交接、CR-R04-R03 执行细则，以及指定 ponytail 5.2.0 审查技能。中文输出遵从本次审查授权。未读 `.env`、DPAPI、KEYS 或 holdout。
- 比较范围 12 个文件；重点为 `network.py`、`http_transport.py`、`dns_resolver.py`、`settings.py`、R03/T08 unit/contract/security 测试，以及仅新增的 `dnspython==2.9.0` 锁定依赖。没有复用作者的测试通过声明作为本次结果。

## 必须修复

### 1. [P1] 跨源 Location 可以重新携带 query 凭据

- 位置：冻结 worktree 的 `backend/src/ai_intel/infrastructure/network.py:368–376`，尤其 `372–376`。
- 触发：可信凭据只授予 `https://registered.example`，注入 `api-key` 和 Authorization；该源返回 `302 Location: https://other.example/next?api-key=<同一合成凭据>&visible=1`，另一个源也在域名白名单。
- 结果：新源的真实 `http.client` 请求仍带此 `api-key` query。Authorization 头被正确剥离，但 `credentials=None` 没有清除 `next_url` 的敏感 query。独立探针 `http[0]` 记录 `cross_origin_query_contains_injected_secret=true`、`cross_origin_authorization_header_present=false`；连接均关闭。
- 影响：域名授权不等于凭据 origin 授权；上游通过 Location 反射凭据时可把专属源密钥送往另一个允许源。这里用合成哨兵与 socket fixture 复现，没有发送真实秘密。
- 最小修复：跨 origin 跳转时从 `next_url` 清除敏感 query 键（大小写不敏感）并清除注入凭据；之后每跳仍做地址检查。不要使用日志用的 `REDACTED` 值作为转发凭据。
- 复验：Location 的不同大小写、percent encoded key、相对跳转后跨源跳转、跨源后跳回原源；第二 origin 无 query/header 秘密，普通 query 保留，同源注入仍可用，所有响应关闭。

### 2. [P2] 公网 A 会提前返回，AAAA 地址从未核查

- 位置：`backend/src/ai_intel/infrastructure/dns_resolver.py:23–59`，尤其 `49–59`。
- 触发：同域名 A 回答为 `93.184.216.34`，AAAA 回答为 `::1`。这也是 system 路径会因混合公网/私网解析拒绝的边界。
- 结果：独立 `mixed_a_aaaa` 探针只观察到一问 `A`，接受公网 A；没有发出 AAAA 问题，无法发现私网 AAAA。现有 DoH IPv6 测试只覆盖 A 空时才问 AAAA。
- 影响：违背 CR 的“原目标所有 IP 验证均保留”；显式 DoH 与 system 安全策略不等价。已连接的 IP 仍固定为公网，本探针**没有证明私网连接或 SSRF 成功**，问题是漏检解析集合。
- 最小修复：在同一绝对截止时间内完成 A 和 AAAA 两问，汇总两个类型的有效回答，先检查整组所有地址，再返回去重集合；任一类型出现非公网地址即拒绝，不能因 A 可用静默跳过 AAAA 错误或缺测。
- 复验：公网 A+私网 AAAA、私网 A+公网 AAAA、双公网、仅 A、仅 AAAA、两问空、第二问超时；保证最多两问，时间和地址总数仍有硬上限。

### 3. [P2] DNS answer 没有绑定查询 owner/CNAME 链，也接受 TC 截断回答

- 位置：`backend/src/ai_intel/infrastructure/dns_resolver.py:39–48`。
- 触发：正确 question/ID/NOERROR，但 answer 只有 `unrelated.example. A 93.184.216.34`；或者 registered→alias→registered 的 CNAME 环再附无关 A；或者设置 `TC` 的 partial A 回答。
- 结果：三个独立探针均返回 `93.184.216.34`。`query.is_response` 校验 QR/ID/opcode/question，不验证 answer 的 owner 或 CNAME；当前提取遍历任何同 rdtype 的 answer。已交叉读取本次锁定依赖的 `Message.is_response` / `QueryMessage.resolve_chaining` 源码。
- 影响：把未回答本查询或不完整的 DNS 材料当作目标域名地址；严格 TLS 仍保留，但 DNS 身份/完整性不能宣称通过。不是凭空猜测 DNS 污染，而是本地执行确定可接受错误 wireformat 语义。
- 最小修复：拒绝 `TC`，使用 dnspython 的 `resolve_chaining()` 只取得本 question 的最终 IN RRset，验证类型/owner/链长度；无对应结果或 CNAME 环转固定 DNS 错误。不要手写一套 wireformat/CNAME 解析。
- 复验：合法 CNAME 正例、无关 owner、错误 class、CNAME 环/过长、CNAME 无末端地址、TC、匹配 question/ID 的空答案。拒绝之前的公网 A 不能算通过。

### 4. [P2] DoH 内层重建 deadline，外层截止后仍开始网络工作

- 位置：`backend/src/ai_intel/infrastructure/dns_resolver.py:27–36` 与 `backend/src/ai_intel/infrastructure/network.py:447–461`。
- 触发：外层预算 50ms，在 `create_network_gateway` 构造（包括创建/装载 CA context）处注入 80ms 的可观察延迟，然后执行内层 fetch。
- 结果：独立探针实际在外层开始后 109ms 才开始内层请求，此时内层仍余 35ms；141ms 才以 `network_timeout` 结束。原因是把剩余时间存为 policy 数值后，内层 fetch 再从当前时刻加上该旧数值。
- 影响：“同总截止时间”不是同一个绝对 deadline；低预算或构造阻塞时可超时继续执行。探针中的构造延迟是显式 fixture，不将其误记为本机真实网络延迟。无需要求强制中断所有 CPU 初始化，也必须禁止原截止后开始新的 IO。
- 最小修复：DoH 复用预构造的固定 resolver transport，并将外层 `RequestDeadline` 对象一路传递到内层 `_fetch` / transport；每次 IO 前校验该对象，不能嵌套生成新绝对截止时间。
- 复验：构造/队列耗尽预算后不得开始 IO；A 后 AAAA、DoH redirect/读体均共享同一截止时间；结合当前阻塞 header/body 与 DNS 并发回归，确认无计时器或 socket 残留。

### 5. [P2] 无 Content-Type 的 401/429 被归为同一个内容错误

- 位置：`backend/src/ai_intel/infrastructure/network.py:378–380` 与 `161–170`。
- 触发：合法 HTTP `401` 或 `429`，`Content-Length: 0`，没有 Content-Type。空错误响应合法且常见，不能按成功文档解析要求处理。
- 结果：独立两个实际 HTTPResponse 探针都抛 `UnsupportedContentTypeError(code=unsupported_content_type)`，异常没有 status_code；调用方不能得到 `classify_http_failure` 所需状态。连接关闭正确。
- 影响：冻结的 429 有限退避与 401/403 永久认证失败不能可靠区分。旧实现对缺 Content-Type 曾保留 HTTP 状态，本候选新增严格成功内容检查时让该空错误响应回归。
- 最小修复：先保留/分类非成功 HTTP 状态，再对成功文档执行类型检查；错误正文仍须有界且不得当成功文档解析。或者使用明确包含原 HTTP 状态/固定分类码的安全错误，避免泄露底层消息。
- 复验：401、403、429、503 的空正文/缺类型、problem+json/不允许类型，以及正常 200 缺类型仍拒绝；无自动重试，不改任务层唯一重试合同。

## 独立命令与结果

工作目录除注明外为冻结 WT 的 `backend`。完整 argv、开始/结束、退出码和原始输出在 `reports/runs/recovery_r03_network_review_1_20261015/`，由 `manifest.json` 索引及摘要。

| 实际命令 | 退出码 | 结果 |
|---|---:|---|
| `uv sync --locked` | 0 | 独立安装；dnspython 2.9.0，无锁文件改动 |
| `uv run --locked pytest tests/unit tests/contract/test_t08_network_redirects.py tests/security/test_t08_network_and_sources.py tests/security/test_r03_network_transport.py --junitxml=.../regression.xml` | 0 | 251 passed，0 failure/error/skip，1 warning；19.86s；coverage 69.89%，原 fail-under=60 未改 |
| `uv run --locked ruff check src tests` | 0 | All checks passed |
| `uv run --locked ruff format --check src tests` | 0 | 125 files already formatted |
| `uv run --locked mypy src` | 0 | 60 source files，0 issues |
| `git diff --check <baseline> <target>` | 0 | 无空白差错 |
| `uv run --locked python review_network_probes.py` | 0 | 探针执行成功；上述错误接受/泄露/超时结果为候选失败，退出 0 **不代表负例通过** |
| `uv run --locked python review_nvd_live.py` | 0 | 两种配置各一次来源尝试；system 在连接前拒绝，DoH 当前独立 NVD 200。详情见下 |
| WSL `cli index_repository --repo-path <冻结WT>/backend/src --name r03_network_review_1_f0e0b19 --persistence false` | 0 | 独立项目 729 nodes / 3129 edges；60 Python 文件，无 partial/unusable/skipped；缓存仓外，不写 `.codebase-memory` |
| 同项目 `get_architecture`、`get_graph_schema`、两次 `trace_path`，以及源码 `rg` | 0 | 图与源码相互核对，没有以图代替源码证据 |

初次 `cli help` 返回 1（unknown tool），随后用二进制 `--help` / `cli <tool> --help` 确认语法。无参数 index 尝试返回 1（repo_path required），一次 `--project_name` 返回 1（正确参数为 `--name`）；这些是工具调用语法错误，未冒充业务测试失败，最终索引如上成功。一次资料读取 cwd 误用 backend 前缀返回 1，随后按冻结 WT 根路径读取成功；一次 Windows rg 文件参数使用通配符返回 1，后续用实际文件路径读取。索引缓存目录经只读目录探测为 `/root/.cache/codebase-memory-mcp`，冻结 WT 没有 `.codebase-memory`。

原有回归实际验证了：全局 unicast/空/混合 DNS 负例；固定 numeric connect 与前后 peer 相等；CA 必须验证、hostname 校验与 SNI/Host；系统代理未读取；逐跳域名和私网拒绝、HTTPS 不降级；大小/type/编码/framing/truncated 处理；关连接；系统 DNS outstanding 工作与同实例请求并发有界；header/body 截止时 shutdown；已覆盖 OSError/HTTPException/证书失败的固定错误码和合成秘密不进 traceback。未增加 skip、未变更门槛或测试数据。

## 当前独立真实 GET

- `2026-10-15T12:16:02.289274+08:00`：system，10s budget，无 API Key，无 fixture；47ms 在连接前抛 `network_policy_violation`，没有 peer/HTTP 请求。没有借 DoH 隐式回退。
- `2026-10-15T12:16:02.330121+08:00` 至 `12:16:03.531841+08:00`：显式 cloudflare_doh，严格 CA/hostname；固定解析器 peer `1.1.1.1`，目标 checked IP/实际 peer 均 `172.65.90.24`；NVD API **200，3105 bytes，1 条 CVE-2024-28224**。
- 原始样本摘要：`e359d3afb76ace80ba752a23d7fe913064d6ef144356ddcf095e1105bee8a5b1`。原文为本次 `nvd_cloudflare_doh.body.json`；response 的 set-cookie 已在收据中显示 REDACTED。
- 来源最多两次尝试（system 未触达 HTTP、DoH 一次来源 GET；DoH 的 DNS HTTPS 问题单独为一问），没有 API Key、付费调用、扫描或 PoC；没有用作者 11:53:40 的样本冒充本次成功。这不是持续采集、PG 保存、Agent/模型 live、吞吐或正式性能。

## 真实入口与验收覆盖缺口

独立 backend/src 索引的 `create_network_gateway` 入边只有 `fetch_with_policy` 与 DoH 解析器内部；`fetch_with_policy` 没有业务 caller。源码 rg 也表明所有工厂/Policy 使用仅在 infrastructure 这三个网络文件内；`ApplicationSettings.dns_resolver` 只是新增配置字段，还没有装配到来源 handler。冻结 `workers/runtime.py` 是运行观测，`ingestion/connectors.py` 是协议/注册检查；不能把探针直接调用网关说成 R04 来源已接通。

T08-C02/C03/C04 已有自动反例证据，但 C05 的新空错误响应暴露缺口；C01 当前只有公共 GET 和 fixture，没有来源上下文/PG 原文保存链；C06 只是原注册 fixture，不代表八类真实来源能力。未复跑执行器 PG/Celery、游标、两个 worker/恢复、其他 R03 子片、R04 浏览器/DB 闭环、收费 API/凭据、真实无效证书站点、长期 DNS/并发压测或跨进程限制。不能据此签整卡。

下一步：主控按问题 1–5 作最小修复并冻结新 SHA；使用新 clean 审查 WT 重跑对应独立探针、原网络回归与必须静态检查。待网络边界通过后，R04 才能把真实来源调用接到它，再分别提供任务/数据库/页面证据。

Verdict: fix 1–5 first；网络候选保留 needs_changes。无需新增抽象层；未发现可量化的纯删行结论。
