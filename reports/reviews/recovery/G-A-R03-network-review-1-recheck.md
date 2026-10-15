# G-A / R03 网络切片初审 1 定向复核

本次改动做了什么：修复初审发现的 A/AAAA、DNS answer/CNAME/TC、绝对 deadline、跨源 query 凭据与空 HTTP 错误分类。**原五项同触发输入已按预期处理；扩展凭据探针仍发现两个必须修复的问题（6、7），当前网络候选保持 needs_changes。**

初审失败报告 `G-A-R03-network-review-1.md` 与原始日志保持原样。本报告不是 R03、T08 整卡或 G-A 的 accepted 签字。

## 固定范围

- 目标 SHA：`59466ceb1703e2741406939adcfb1196e20c77d2`；tree：`9c35d7c614fcff6184491022e93a9ecde3e5e52c`。
- 复核前对象：`f0e0b19df2813339138c5f727b4051eb794f9f78`；直接修复 diff 为 `59466ce^..59466ce` 的 7 个源/测试文件及 CR 记录。两个 SHA 之间还有其他任务合并，本次不把那些文件记成已审查。
- 独立 clean WT：`C:/Users/yinha/.codex/worktrees/recovery-r03-network-recheck/dianzi`；分支 `codex/recovery-r03-network-recheck`。不使用 root 可变 checkout 的业务代码、测试结果或后续 `48ad` 作为本目标的证据。
- 已读冻结 AGENTS、执行地图、R03/T08 约束、状态/交接与新 CR 修复说明；沿用已读取的 ponytail 5.2.0 审查技能。所有命令、秒级 `+08:00` 起止、退出码与最终封存时刻在运行目录 manifest。
- 独立探针只在自己的 WT 写入；业务、合同、schema、锁、progress 无改动，无 commit/push。未读取 `.env`、DPAPI、KEYS 或 holdout，无秘密、付费 API、扫描、PoC 或 Docker 操作。

## 原五项复核结果

使用初审独立 `review_network_probes.py`，只为 fixture gateway 增加真实 API 的 `deadline` 关键字；原负例输入和预期拒绝/不转发判据保持。合法 CNAME 正例的新增 AAAA 问题返回 CNAME+NODATA（之前只问 A，AAAA 分支不可达），避免让一个 A RRset 冒充 AAAA 回答。此 harness 适配不是修改项目测试或金标。

| 原问题 | 当前实际结果 | 证据 |
|---|---|---|
| 1 跨源敏感 query | 第二个实际 http.client 序列化中无合成 query secret、无 Authorization；状态 200，两响应关闭 | `independent_negative_probes.json` → `http[0]` |
| 2 漏查 AAAA | A 与 AAAA 两问均出现，A 公网+AAAA `::1` 抛 `network_policy_violation` | 同文件 `dns[1]` |
| 3 owner/CNAME/TC | 无关 owner、环+无关 A、TC 均抛 `network_dns_error`；合法 CNAME A+AAAA NODATA 返回原公网 A | 同文件 `dns[0,2,3,4]` |
| 4 deadline 重置 | 外层 50ms/构造延迟 80ms后抛 `network_timeout`，没有进入 transport.request；factory receipt 没有 network_started 字段 | 同文件 `deadline` |
| 5 空 401/429 | 两个实际 HTTPResponse 保留 401/429；连接关闭；项目新增用例也验证空 body 和 Retry-After | 同文件 `http[1,2]` + 原回归 |

deadline 探针整个调用用了约 94ms，因为注入的构造阶段阻塞 80ms；修复确认的是**截止后不再启动新的网络 IO**，并非谎称该同步 CPU/初始化调用在 50ms 内返回。内层传递绝对 deadline、取 min 与 numeric IP 直接解析均交叉源码验证。

CR 把 fixture 非 2xx `reads==1` 改为 `reads==0`，本次核对这是“错误正文不读”的明确新行为：原状态、一次请求、关闭断言保留，并新增 `body==b''`。没有通过扩大阈值、修改分母或 skip 获得通过。

## 必须修复

### 6. [P1] 混合大小写 Bearer 仍能通过改名 query 泄露 token

- 位置：冻结 `backend/src/ai_intel/infrastructure/network.py:377–380`，尤其 `379`。
- 触发：仅配置 `Authorization=SecretStr('bEaReR <合成token>')`，无 query 凭据；302 Location 为另一白名单 origin 的 `/next?renamed=<同一token>&visible=1`。
- 实际结果：第二个 http.client 请求仍带 token，Authorization 头没有转发。`independent_extended_probes.json` 的 `http[3]` 显示 `cross_origin_query_contains_injected_secret=true`；连接关闭正确。它不是无效认证格式：HTTP 认证 scheme 大小写不敏感，见 [RFC 9110 §11.1](https://www.rfc-editor.org/rfc/rfc9110.html#name-authentication-scheme)。
- 原因/影响：只用 `startswith('Bearer ')` 收集去 scheme 的 token，合法 `bearer`/`bEaReR` 未收集；Location 改名反射可把凭据送往其他 origin。没有发送真实秘密或外网请求。
- 最小修复：用大小写不敏感的 scheme 判断，在原值上提取/strip token（如 `partition(' ')` 后对 scheme casefold），不要对 token 本身转小写；继续保持跨源 header 与 query 剥离。
- 复验：标准 Bearer、全小写、混合大小写、合法多空格分隔，无 query 凭据也不泄漏；改名 query、原敏感 query、路径反射与同源注入分别验证。

### 7. [P2] URL 编码的已知 secret 仍进入“脱敏”响应元数据

- 位置：`backend/src/ai_intel/infrastructure/network.py:146–162`，尤其 `160–161`。
- 触发：api-key header 配置合成值 `review/synthetic+credential==`；成功响应 Content-Location 的 `renamed` query 或 X-Trace-Echo 中反射 `review%2Fsynthetic%2Bcredential%3D%3D`。
- 实际结果：原串未出现，但对 `FetchResult.redacted_headers` 进行一次 `unquote` 就恢复该秘密；两个字段的 `encoded_secret_recoverable` 都为 true。证据为独立 `header_redaction_probe.json`，状态 200、连接关闭。
- 原因/影响：新增保护只 `replace` 原始 secret 字符串，没有识别编码表示；之后可被调用者当“已脱敏元数据”记录，违反秘密不进日志/录制响应的边界。这里只运行合成 fixture，没有实际日志凭据泄漏。
- 最小修复：若安全 URL 解码后的 header 值含已知 secret，则整值 REDACTED，或替换原文与其规范 percent encoded 表示；不能输出解码后的原秘密，不能修改/伪装原文 body。
- 复验：原串/URL 编码/大小写 hex、Content-Location/Location/普通响应头均不再可恢复已知秘密，普通值与已有 set-cookie 脱敏保持。

## 独立执行与原始覆盖率

运行目录：`reports/runs/recovery_r03_network_review_1_recheck_20261015/`。以下均在新冻结 WT 执行，未复用作者日志；探针 exit 0 只表示运行成功，逐项真假值才是业务判据。

| 实际命令 | 退出码 | 当前结果 |
|---|---:|---|
| `uv sync --locked` | 0 | 独立锁定安装，锁未改 |
| `uv run --locked pytest tests/unit --cov-report=json:<run>/unit_coverage.json --junitxml=<run>/unit.xml` | 0 | **254 passed，0 fail/error/skip，1 warning，32.77s** |
| 纯 unit JSON 原始门槛核查 | 0 | **2307/3778 = 61.064055055584966% ≥ 60**；不是依赖插件 precision=0 的退出码或整数显示值 |
| `uv run --locked pytest tests/unit tests/contract/test_t08_network_redirects.py tests/security/test_t08_network_and_sources.py tests/security/test_r03_network_transport.py --cov-report=json:<run>/regression_coverage.json --junitxml=<run>/regression.xml` | 0 | **327 passed，0 fail/error/skip，1 warning，17.65s；原始 2516/3812 = 66.00209863588667%** |
| `uv run --locked ruff check src tests` | 0 | All checks passed |
| `uv run --locked ruff format --check src tests` | 0 | 138 files already formatted |
| `uv run --locked mypy src` | 0 | 64 source files，0 issue |
| `uv run --locked python review_network_probes.py` 原探针与扩展探针 | 0 | 原五项预期通过；扩展问题 6 失败 |
| `uv run --locked python review_header_redaction_probe.py` | 0 | 问题 7 失败，两个编码恢复判据 true |
| `git diff --check HEAD^ HEAD` | 0 | 当前修复 diff 无空白错误 |
| 新 CBM index / architecture / schema / 两次 trace + 源码 rg | 0 | 独立固定项目及调用入口核对 |

第一次 PowerShell `ConvertFrom-Json` 读取 coverage JSON 因空 context key 拒绝，之后使用 `-AsHashtable` 成功取得上述原始值；这是取证读工具语法问题，不是测试失败，也没有重写 JSON。`coverage_raw_gate.json` 保留完整分子分母和原门槛 60。本报告不使用另一候选 59.98/61.42 的数值给 59466 背书。

## 调用入口、live 与验收限制

独立 index 名 `r03_network_recheck_1_59466ce`，只索引冻结 `backend/src`，813 nodes/3584 edges/64 Python 文件，无 partial/unusable/skipped；仓外 `/root/.cache/codebase-memory-mcp`，`--persistence false`。`get_architecture`、`get_graph_schema`、两次 `trace_path` 与源码 rg 交叉：工厂仍只有 legacy fetch 与 DoH 内部调用，`fetch_with_policy` 没有业务 caller，settings 的 dns_resolver 尚未装配到 R04 来源 handler。

本轮真实外网 GET **not_run**；已发现问题 6/7，保留公共探测额度用于后续安全修复候选。没有引用作者 12:24 NVD 200 或初审的当前成功作为本目标独立 live。没有验证 PG 原文保存、队列/游标、双 worker/宕机恢复、R04 浏览器闭环、模型/收费/凭据、长期并发或正式性能；网络切片修复也不能签整卡。

下一步：主控修复问题 6/7 并冻结新候选；同一独立 reviewer 在 clean WT 重跑这两个扩展探针和相关原负例、原始 unit 60% 门及必要静态/网络回归。保留本次失败，不覆盖报告。

Verdict: fix 6 and 7 first；59466 网络候选 needs_changes。原五项定向验证通过不等于全部凭据边界通过。
