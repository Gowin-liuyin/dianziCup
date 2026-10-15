# G-A / R01-search-TLS · 独立审查 1

What this change does: 本切片把受信 CA、独立搜索凭据和只读证书挂载接入开发安全搜索，保留明确的 HTTP 测试 overlay。应用通过真实 HTTPS 健康请求区分搜索 ready 和安全失败。

审查意见：**needs_changes**。正确 CA、证书主机名和健康专用账户已经独立跑通；七条真实 TLS/故障案例通过。但新增测试的失败输出仍泄漏测试密码，现有 CI 也没有准备其 TLS fixture。两个已证实问题均阻断本切片验收。本审不改业务源码、合同、阈值、金标、状态，不签 accepted，不签整 R01/T03/G-A，不提交或 push。

## 冻结输入、依据和范围

审查者未参与本切片实现。源工作树 `C:\Users\yinha\.codex\worktrees\recovery-r01-tls\dianzi`，分支 `codex/recovery-r01-tls`；开始、09:58 取证和真实测试后 `git status --porcelain` 均为空。主仓已有修改保持原状；本审只写本报告和 `reports/runs/recovery_r01_search_tls_review_1_20261015/`。

| 对象 | commit | tree |
|---|---|---|
| 输入 baseline | `adb86df7149d2f753f4afe1e08d721160dd780fe` | `2d524bfa6dc367c4b648f24d8e81ba2e52a7f7b4` |
| 首次源码交付 | `67246e60b2605cf4025ef4502d5140a9353f6a9c` | 本审按最终版本复跑，未给该版另计通过 |
| 最终源码 | `741e5da9f21b95448a03666fff881f1843cbc606` | `3f7f8a7bad60cf1efc6e28614e5a69e6a31dc318` |
| 作者证据 HEAD / 实际复跑输入 | `4b4b9763dc0b75594864b3893dc95a215861d594` | `5a6c8349f36b08aa446855511dc1f3088b5c6aa3` |

baseline 祖先核对 exit 0；最终源码到证据 HEAD 的 backend/infra/config/scripts/.github 差异为空，exit 0。源码 diff-check exit 0。原始记录见 `source_trees.json/.log`、`source_ancestry.json`、`code_evidence_match.json/.log`、`source_identity.json/.log`、`source_diff.json/.log`、`source_diff_check.json/.log`。

已读当前插件 `C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md`、AGENTS、00 执行地图、恢复 R01、原 T03、02/03/05/09 合同、当前状态/交接、`G-A-R01-runtime-review-1.md` 的 Must2 和作者 `R01-search-TLS.md`。作者结论只用于定位材料。审查覆盖完整应用入口及调用关系，包含已在 baseline 的 ssl/settings；旧 PG 认证和 0006 装配不在本包通过范围。

本审使用官方 CBM CLI **0.11.0**，独立仓库外 cache `/tmp/dianzi-cbm-r01-search-tls-review-1-20261015`，仅索引源工作树 `backend/src`，`persistence=false`。实际 540 nodes/2059 edges，not-indexed/skipped/partial/unusable 均 0；help、graph schema、app outline、`trace_path(create_application,outbound,depth=3)` 均有独立 receipt。CBM 显示 factory 到 health router/settings 的路径，动态健康闭包和 HTTPX 调用另以源码及 rg 交叉核查，未将静态图当运行成功。`origins.log` 确认 app/settings 实际导入均来自固定工作树。

## Must fix

1. **SecretStr 之外的临时变量仍把 TLS 测试密码写进失败报告**（P1；`backend/tests/integration/test_r01_search_tls_live.py:44`、`:65`、`:73`；`backend/tests/conftest.py:23`）。
   - **这是什么：**fixture 的最终 dataclass 用 SecretStr，但前置 `configured` 字典存放普通密码字符串；测试又把密码解包到局部普通 `password`。现有共享报告 hook 只脱敏 PostgreSQL/Redis 连接串。
   - **复现与实际问题：**在已恢复健康的 TLS 服务上，只把 fixture 的测试密码替换为随机错误值，选择 `correct` case，执行 `pytest … -k correct --showlocals --no-cov --junitxml=…`。10:02:00–10:02:05 实际 exit 1、1 failure/0 error/0 skip；pytest 的局部变量输出和 JUnit 都包含完整随机错误密码。原始输出包含检查为 stdout=true、JUnit=true，见 `forced_failure_showlocals_recovered.json`；保存的 `.log/.xml` 已在写盘前脱敏。输入错误端口 29203 加 `--showlocals` 另会在 fixture 错误报告显示 `configured` 中的密码片段，见 `fixture_failure_showlocals_full_retry.json` 和 `prior_output_fragment_audit.json`。pytest 的 repr 截断不是秘密保护。
   - **最小修复与复验：**前置配置和测试局部变量保持 SecretStr，避免将解包后的明文长期留在可展示局部变量；共享报告 hook 增加 TLS 凭据保护。补一条故意失败的子 pytest 回归，同时检查 stdout/JUnit 的完整密码和截断片段，涵盖 fixture 输入错误与业务断言失败、`--showlocals`。密码泄漏负例必须不改 outcome/count，也不能只在外层作者 runner 写日志后做替换。
   - **不修的影响：**TLS 正例全绿时隐藏的秘密边界问题，会在故障诊断或 CI 开启 locals 时暴露有效 fixture 凭据。默认不带 `--showlocals` 的两个独立失败检查未出现完整值泄漏；本 finding 限定于实测失败输出条件，不声称产品健康响应泄密。

2. **新增 TLS 集成测试缺少 CI 资源装配，现有 integration 必然被 blocked error 截断**（P1；`.github/workflows/ci.yml:32`、`:84`；`scripts/dev.py:162`；`backend/tests/integration/test_r01_search_tls_live.py:37`、`:48`、`:108`、`:120`、`:134`）。
   - **这是什么：**CI 创建 HTTP security-off 测试项目，然后共享入口运行整个 `tests/integration`。新增七例属于这个目录，但 workflow 没有配置五个 `TEST_SEARCH_TLS_*` 输入、PKI/security 初始化或安全搜索服务。
   - **复现与实际问题：**独立取消 `TEST_SEARCH_TLS_PASSWORD`，选择正确 CA case，09:54:55–09:54:58 实际 exit 1、1 error/0 skip，错误明确 `blocked: isolated secure OpenSearch TLS resources required`（`missing.json/.log/.xml`）。rg 确认 workflow/scripts/conftest 均未提供 TLS fixture；tests 的 URL/socket 和故障容器还固定本轮 29202、`dianzi-test-r01_tls_20261015`。这是确定的 CI 输入缺口；GitHub 云执行本轮 not_run，不能伪称云失败已实跑。
   - **最小修复与复验：**在 CI 提供显式隔离 TLS fixture，用固定镜像、仓库外 PKI、健康只读账户和真实 CA/hostname 校验初始化；把测试连接/容器身份接入经验证的 fixture 输入，停止前继续核对真实 Compose label。注册 `real_search_tls` marker。按实际全 integration 入口复跑，必须包含七例安全 TLS；不能删测试、改 skip 或排除 marker 得到假绿。
   - **不修的影响：**本地专用资源上的七例通过不能保证当前 workflow 可运行。本任务新检查还不能满足 09 合同“进入 CI”的要求。作者报告已把共享 conftest/CI 留给主控，这说明修改归属，不解除本切片验收依赖。

没有单列风格偏好、猜测性能瓶颈或无具体输入的复杂度问题。stdlib SSL、HTTPX BasicAuth、固定配置及既有报告 hook 足以解决这里的工作，不需要新框架或 TLS 实现。

## 独立测试与实际入口

所有时间为 2026-10-15、Asia/Shanghai。执行 cwd、完整 argv、秒级起止、exit、JUnit 计数、输入 commit/tree 与原始日志见同名 JSON/log/XML；主要入口是报告目录自有 `review_checks.py`，它不会写冻结源码。

| 检查 | 实际窗口 +08:00 | 结果 |
|---|---|---|
| 全 unit，原覆盖门不变 | 09:53:09–09:53:17 | 63 pass/0 fail/error/skip，exit 0；64.83% ≥ 60% |
| 原 19 + 新 5 Compose 配置合同 | 09:53:09–09:53:26 | 24 pass/0 fail/error/skip，exit 0；不启动服务 |
| 全 security | 09:58:07–09:58:14 | 63 pass/0 fail/error/skip，exit 0 |
| Ruff / format | 09:53:09–09:53:10 | 各 exit 0 |
| mypy，显式 backend 配置 | 09:53:09–09:53:17 | 50 source files，exit 0 |
| OpenSSL 公共证书验证 | 09:56:50 | 正确 CA+localhost exit 0；wrong CA / IP SAN mismatch 各 exit 2 |
| 健康账户权限和真实 TLS | 10:02:00–10:02:03 | health=200/green；GET `/`、索引列表、安全用户接口各 403；CERT_REQUIRED、hostname=True |
| 七条真实 TLS/故障恢复 | 10:02:11–10:03:26 | 7 pass/0 fail/error/skip，exit 0；72.85 秒 pytest 时间 |
| 默认环境加载的 `ai_intel.api.app:app` | 10:05:02–10:05:06 | exit 0；search ready，PG/Redis not_configured，整体 503/not_ready |

非 unit 选定测试使用 `--no-cov`，没有变更原 unit 60% 门。故意错误密码、错误 fixture 和缺 fixture 的失败另列，不计入成功七例，也不改变分母。warning 保留：Starlette 弃用提示及未注册 `real_search_tls`；没有关闭 warning。

真实七例验证：正确 CA+独立凭据 search ready；no CA、wrong CA、hostname 改用未列入 SAN 的 IP、错误密码均固定安全 `search connection unavailable`/503；实际 SSL socket 验证 localhost/opensearch SAN、hostname 和 CERT_REQUIRED；只停止本包搜索容器时同样安全 503，finally 启回并等严格 CA 健康检查恢复。产品响应未包含随机密码或 traceback。

`default_entry_probe.py` 在导入默认应用前从本包测试环境显式映射四个 OPENSEARCH 配置，通过实际模块级 app 路由执行健康请求。它没有 PG/Redis 输入，因此总体 503 是正确行为；本审没有将 search 分项 ready 称为整体 ready。

## 部署、安全和资源边界

完整 diff 与调用方核查确认：base API/worker/scheduler 使用 HTTPS、同一只读公共 CA、独立 username/SecretStr password；HTTP test overlay 显式移除应用认证/CA 配置、移除搜索 TLS bind，并明确 security-off 用途。secure host 入口保留安全插件，内部 loopback 监听、清空 published ports。公共 opensearch.yml 不含私钥/账号 hash，禁止 demo/default security index 初始化；节点和管理员证书 DN 分开。官方 2.17 文档要求 TLS PEM/PKCS#8 与管理员证书隔离，`-nhnv` 是关闭 hostname 的参数；本配置和运行命令未使用该参数或 curl -k。[TLS 配置](https://docs.opensearch.org/2.17/security/configuration/tls/)、[securityadmin](https://docs.opensearch.org/2.17/security/configuration/security-admin/)。

准备脚本来源核对为固定批准 OpenSearch digest 中的 `hash.sh -env` 和安全配置模板，随机密码不进入 argv；重写 users/roles/mapping 后健康角色只有 `cluster:monitor/health`。独立只读权限请求已经验证该账户不能列索引或读取安全账户。脚本拒绝仓库/build context 内目录和既有目录，umask077；当前私有目录 root700、connection root600、CA/admin key root600、节点 key 1000:1000/600、security 1000:1000/700。公有证书 644；私钥没有进入应用 mount。没有读取私钥正文、其他 connection、用户 DPAPI/provider keys、holdout、.env 或附件 KEYS。

独立 fresh PKI 生成/operator 初始化 **not_run**：本审的容器操作授权仅允许既有本包 TLS 服务 stop/start，不新增 operator 或重建容器。已核对准备源码、当前文件权限、公有证书链以及实际安全服务；不拿作者 recipe 运行日志补成独立生成通过。当前 node 公有证书有效期到 2026-10-18T02:19:10+08:00；父资源授权更早于 2026-10-17T21:49:15+08:00 截止，本审未延长。

09:53:09–09:53:10 首次 inspect 实际 exit 1，daemon 不可达；09:56:50 的 ss 没有 TLS listener。不是软件修复/连续稳定性证据。主控授权的 recovery Agent 恢复 daemon 后，10:00:05 当前容器实际 exited/Pid0/Exit255，旧 health log 还停留 02:41，未据旧记录叫 healthy。本审只启动 `dianzi-test-r01_tls_20261015-opensearch-1`，10:00:32–10:00:33 exit 0；10:00:34–10:01:34 独立等待得到新 healthy，再执行本轮实测。没有把 02:xx 到 09:xx 的时钟间隔计入持续运行。

终检 10:03:36–10:03:37：同 project/固定镜像、UID1000、2 GiB、0.5 CPU、256 PIDs、running/healthy、OOM=false、TLS/config bind 全 RW=false、独立 named volume。真实 ss 只看到 IPv4-mapped 127.0.0.1:29202/29302。heap512/mmap off 的配置与冻结 Compose 相符；没有吞吐或持续容量结论。

本审没有操作旧七服务 `dianzi-test-r01_infra_20261015`、其他项目或裸库；没有 pull/build、删卷、downgrade、改系统限额或开启付费调用。10:03:37 后结束容器操作，已向主控明确交回唯一 TLS 项目操作权，无后台复跑。随后仅公有证书和默认 app 的只读健康请求。

## 输出边界、限制与交接

审查 helper 首轮只匹配完整秘密，漏掉 pytest 截断显示的片段；首次 `false` 不能作为无泄漏证据。发现后已对两份自有 log/XML 清理并保留 `prior_output_fragment_audit.json` 的真实发现记录；后续在写盘前检查完整值及 8 字符片段并脱敏，`forced_failure_showlocals_recovered` 给出明确双通道 true。不提供明文失败输出或真实凭据值，复现保留输入形状、源行号和失败/count。

初期只读定位有不存在文件/错误 cwd，以及一次 CBM 工具名误用；随后按 0.11 help 使用 `trace_path`，相应失败未记成业务测试通过。可选删除本审生成的 pytest/mypy 缓存被自动审批拒绝（blocked by policy），没有删除或绕过；缓存不属于交付 manifest，不需要扩展权限。完整测试日志和 XML保留。所有原始失败均未改成 skip。

未运行：GitHub 云 CI、安全 base 完整七服务冷启、完整 PostgreSQL/Redis/T03 集成、新 PGauth/0006、UI/e2e、模型/FOFA/外部来源 live、正式评测/性能/稳定窗口、人工最终验收。独立通过仅支持 E1/R2 的搜索 TLS 工程切片；不认证评分整项、整卡或整阶段。

下一步先修 1、2，冻结最小补丁后由非作者定向复验失败输出与全 integration/CI fixture，再交新阶段 reviewer 审集成 G-A。不改公共合同、计分分母或 unit 门。

**Verdict: fix 1 and 2 first.**

Not checked: 云 CI、全安全七服务部署、PGauth/0006、UI/模型/外部来源、正式评测/稳定性与人工验收。
