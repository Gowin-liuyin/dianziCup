# G-A / R03 网络切片初审 1 第二次定向复核

本次改动做了什么：按不区分大小写的 Bearer scheme 提取已知 token，token 自身大小写保持；对一次 URL 解码可恢复已知秘密的响应头整值 REDACTED，原文 body 不变。

结论：**冻结 `2522b3a` 的七项网络修复定向独立检查通过。此次有界复核没有仍可复现的阻断问题。** 只支持记录这个网络技术切片的检查通过，不签 R03、T08 整卡、R03:T08 全部来源能力或 G-A accepted；真实业务来源入口尚未接入。前两次 needs_changes 报告及失败证据保留，不覆盖。

## 固定对象与权限

- SHA：`2522b3a941030f373ccd1736bd54cee411e939a9`；tree：`8b8c5bebe29e12cf628d094ed474d4d61ae002be`；本次修复父提交：`08c2ff0f8ebcb4e5a0cc3c32d390bdb9518898c0`。
- 直接修复范围 `2522b3a^..2522b3a`：network.py 两处、test_r03_network_transport.py、CR 与作者证据。本次也复跑冻结版本相关单元/合同/安全回归，没有给两次候选之间其他业务合并作完整 review。
- 独立 worktree：`C:/Users/yinha/.codex/worktrees/recovery-r03-network-recheck-2/dianzi`；分支 `codex/recovery-r03-network-recheck-2`。从固定提交 clean 建立，Git reflog 创建时刻 `2026-10-15T12:56:23+08:00`。
- 已核对冻结 AGENTS、执行地图、R03 卡、原 T08/引用合同、状态/交接及新增 CR；沿用指定 ponytail 5.2.0 审查技能。未使用 root 可变业务代码或包含未提交 NVD 的 396 项作者结果作背书。
- 只写自己的独立 probe 和获准 root 报告/日志；业务、测试、schema、合同、锁、progress 受保护 diff 为空。未 push/commit，未读 `.env`、DPAPI、KEYS、holdout 或实际秘密值，未执行付费 API、扫描、PoC 或 Docker。

## 独立可观察复验

本次复用初审及第一次复核的独立输入，不只读取作者日志。fixture gateway 的 deadline API 适配与合法 CNAME 的 AAAA NODATA 分支沿用第一次复核，不改变负例输入或拒绝/不外传的判据。socket fixture 通过实际 http.client 序列化请求；fixture 从未计作外网成功。

| 编号/边界 | 2522b3a 实际结果 | 独立证据 |
|---|---|---|
| 原 1 跨源 query 凭据 | 原敏感 query 不转发，Authorization 不转发，第二 origin 正常响应，连接关闭 | `independent_probes.json` → `http[0]` |
| 原 2 公网 A+私网 AAAA | 两问均执行，AAAA `::1` 触发固定 policy violation，未到源连接 | 同文件 `dns[1]` |
| 原 3 owner/CNAME/TC | 无关 owner、CNAME 环+无关 A、TC 被固定 DNS 错误拒绝；合法 CNAME+A 与 AAAA NODATA 被正常接受 | 同文件 `dns[0,2,3,4]` |
| 原 4 绝对 deadline | 50ms 外层预算，构造延迟 80ms，最后 timeout，transport.request 从未开始 | 同文件 `deadline` |
| 原 5 空 401/429 | 保留真实 HTTP 状态，关闭连接；项目回归另验证 403/503、Retry-After、不读错误 body/不自动重试 | 同文件 `http[1,2]` + regression |
| 新 6 混合大小写 Bearer、无 query 凭据 | 原 `bEaReR` 改名 query 输入第二 origin 无 token/Authorization；项目四种 scheme/多空格×两 Location×有无 query 分支通过 | 同文件 `http[3]` + regression |
| 新 7 编码响应秘密 | 原 Content-Location、X-Trace-Echo 一次解码均不可恢复 secret；整值 REDACTED；原 body `b'ok'` 保持 | `header_redaction_probe.json`、`header_body_integrity_probe.json` |

源码交叉位置：`network.py:148–164` 的编码 header 守卫，`network.py:379–384` 的 scheme/token 提取。原跨源 query 剥离、公共 IP/实际 peer、SNI/Host、严格 CA、协议/端口、重定向逐跳再检查、硬读体/并发限制、关闭连接和固定安全错误仍保留。

deadline 注入探针整个调用约 110ms，其中构造 fixture 故意阻塞 80ms；检查证明截止后没有启动网络 IO。没有把同步初始化阶段描述为能在 50ms 内被强制中断，也没有把 fixture 的耗时记作真实网络性能。

## 真实命令与覆盖率门

全部从独立冻结 WT 的 backend 执行（Git/CBM/rg 从 WT 根执行）。逐条完整命令、工作目录、秒级 `+08:00` 起止、退出码、JUnit/coverage 原文件与摘要见 `reports/runs/recovery_r03_network_review_1_recheck_2_20261015/manifest.json`。

| 实际命令 | 退出码 | 结果 |
|---|---:|---|
| `uv sync --locked` | 0 | 独立锁定安装，无锁改动 |
| `uv run --locked pytest tests/unit --cov-report=json:<run>/unit_coverage.json --junitxml=<run>/unit.xml` | 0 | **283 passed，0 fail/error/skip，1 warning；pytest 30.85s** |
| 纯 unit 原始 JSON 门检查 | 0 | **2364/3871 = 61.06949108757427% ≥ 原 60**，不用整数 precision 或仅 exit 0 代替 |
| `uv run --locked pytest tests/unit tests/contract/test_t08_network_redirects.py tests/security/test_t08_network_and_sources.py tests/security/test_r03_network_transport.py --cov-report=json:<run>/regression_coverage.json --junitxml=<run>/regression.xml` | 0 | **379 passed，0 fail/error/skip，1 warning；18.44s；2575/3905 = 65.94110115236876%** |
| `uv run --locked ruff check src tests` | 0 | All checks passed |
| `uv run --locked ruff format --check src tests` | 0 | 140 files already formatted |
| `uv run --locked mypy src` | 0 | 64 source files，0 issue |
| `uv run --locked python review_network_probes.py` | 0 | 原五项及问题 6 的独立判据正确；关闭/secret 字段核对实际真假值 |
| `uv run --locked python review_header_redaction_probe.py` | 0 | 问题 7 不再可恢复；补充 body integrity 结果 true |
| `uv run --locked python review_nvd_live.py` | 0 | 当前候选独立一次公开无秘密 NVD GET 成功，见下 |
| `uv run --locked python ../scripts/security_scan.py --repository-root <WT>` | 0 | 19 个既有模式命中均为精确审查过的 synthetic fixture，无拒绝命中；实际秘密 exact scan **not_run** |
| `git diff --check HEAD^ HEAD` | 0 | 本修复 diff 无空白差错 |
| CBM index/architecture/schema/trace 及源码 rg | 0 | 独立固定 src 索引与真实 caller 相互核验 |

unit 命令收据为 `12:57:25.6647833–12:58:02.6403228+08:00`；混合回归为 `12:59:11.6659099–12:59:32.5912336+08:00`。原始覆盖率与分子分母保存在 `coverage_raw_gate.json`；阈值 60、金标、分母定义和 skip 未改。原 fixture 错误正文 reads 0 的冻结行为继续保留，不恢复成读取错误正文。

秘密模式扫描使用冻结仓库现有 scanner 和精确分类表，原 SCAN_ROOTS/扩展名未调整；它不扫描未注入的真实秘密 exact 值，也不是“任何秘密形式均不存在”的声明。新增 probe 的固定文本均为显式合成输入，本轮不把它们作为在线凭据。实际取样只使用公开来源，返回 set-cookie 已 REDACTED。

## 当前候选独立真实 GET

`2026-10-15T12:59:56.740643+08:00` 至 `12:59:58.033784+08:00`，显式 cloudflare_doh，10s 来源总预算，无 API Key、无 fixture、无代理/私网/CA降级。A/AAAA 两次解析 HTTPS 的 checked/实际 peer 均为 `1.1.1.1`；来源 checked/实际 peer 均为 `172.65.90.27`，TLS 要求 CERT_REQUIRED 与 hostname 校验。

NVD 返回 **200、3105 bytes、1 条 CVE-2024-28224**；样本 SHA256 为 `7d9ca8ede7ef8aa222061b8b297123eab608413f40f422ed26ce55e42f8fafd8`，保存为当前 run 的 `nvd_cloudflare_doh.body.json` 与 `nvd_live_receipt.json`。这是本次实际取样，不复用初审或作者样本。

来源 GET 只执行一次（DNS HTTPS 查询另两次）；没有后续 batch。默认 system 的来源实际 GET 本轮 not_run；system 路径私有/保留地址拒绝继续有自动回归证据。本样本不能充当持续采集、PG 入库、正式性能或 R04 端到端通过。

## 范围缺口与资源交接

本次独立 index `r03_network_recheck_2_2522b3a` 仅 `backend/src`，819 nodes/3616 edges/64 Python 文件，无 partial/unusable/skipped；仓外 cache、persistence false。factory 两个 caller 仍只有 legacy fetch 和 DoH 内部，legacy fetch 无业务 caller；源码 rg 也证明 ApplicationSettings.dns_resolver 没有被 R04 handler 装配。业务入口未接通不能称来源系统 live 已通过。

评分项只登记：E1 的此网络/秘密边界自动与真实出口样本证据；F1 的公开 NVD 原始取样与时间/hash。P1 持续时效/吞吐不登记。T08-C01 的完整来源上下文与业务原文存储、来源调度/注册能力、PG/Celery 执行与游标、双 worker/宕机恢复、R04 数据库/浏览器链、模型/收费凭据、长期并发和正式性能均不由本报告验收。

全部测试/工具进程已完成，未启动服务或 Docker，无需停止共享服务。三个由该 reviewer 创建的独立 CBM cache 项目在 `13:03:38–13:03:46+08:00` 逐一 delete_project，退出码均 0；架构/trace/源码证据已保留。保留审查 WT 与分支供代码定位，不做仓库清理或删除用户文件，结束后释放 agent 槽。

下一步：主控可记录“2522 网络七项修复定向检查 passed”；R04 在自己的有界任务中接真实来源入口，并提交任务/数据库/页面证据。未修改 progress，不直接把原任务或阶段记为 accepted。

Verdict: 本次网络修复定向检查通过；完整任务与阶段仍未验收。
