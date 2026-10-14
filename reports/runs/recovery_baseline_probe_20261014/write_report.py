"""Write a timestamped evidence report for the delegated read-only work package."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    target = root / "reports/reviews/recovery/G-A-baseline-probe.md"
    local_zone = timezone(timedelta(hours=8))
    started = datetime.now(local_zone).isoformat(timespec="seconds")
    report = """# G-A · R00 真实基线复核与 R01 资源准备

状态：awaiting_review；只读复核完成，不签产品 accepted。主控委派：`/root/baseline_runtime_probe`。

文档首次创建时间：{started}
本次写作开始时间：{started}
本次写作结束时间：{ended}
最后更新时间：{ended}
复核实际开始/结束：2026-10-14T20:45:03+08:00 / 2026-10-14T20:53:56+08:00
证据截止时间：2026-10-14T20:53:56+08:00

## 1. 版本、范围与边界

首次实测分支为 `main`，HEAD 为 `8e265dc039a67319140f003f6a070ea714bf7bef`，origin fetch/push 均为授权地址 `https://github.com/Gowin-liuyin/dianziCup.git`。当时用户原有未跟踪恢复计划、提示词、旧审计及其日志得到保留。20:53:07 的主控文档基线已成为 `codex/full-delivery-recovery@b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b`；本轮所查 `backend/src` 的 Git tree 仍为 `b04281bad135540771ce9104302e87c6e5bbb19b`，产品 diff 为空。

读取了 AGENTS、新版 Ponytail 5.2.0、00/02/03/04/05/07 合同、11/12 恢复计划、原审计、状态/交接/阻塞，以及 R00/R01 与 T02/T03/T06/T09/T10/T16/T18/T21/T40 原卡。复核生产入口、解析、模型、事实、游标、认证与前端；未修改业务代码、状态、schema、依赖、配置，没有 commit 或 push。没有读取 `.env`、KEYS-AND-USAGE、秘密附件或 holdout 答案；环境只输出变量名称集合，不输出值。

新增内容仅为本报告和 [原始证据目录](../../runs/recovery_baseline_probe_20261014/)。复用既有 TestClient、解析器、认证/账本/游标服务与旧官方 NVD 留档；新增探针是为了覆盖原有合成测试未检查的真实输入和重启边界，不添加产品依赖。

## 2. 逐问题复核

详细观察见 [behavior_probes.json](../../runs/recovery_baseline_probe_20261014/behavior_probes.json)。以下结果均来自本轮实际执行，不沿用旧审计的通过声明。

| ID | 触发输入与预期 | 当前实际结果与根因 | 影响与最小下一步 |
|---|---|---|---|
| BP-01 | 默认 `ai_intel.api.app:app` 应注册认证与实际业务；匿名 me 应401 | OpenAPI 只有 `/health/live`、`/health/ready`；me404、ready503。`api/app.py:47` 调 `create_application()` 未传认证，工厂只条件挂载 | R01 装配真实依赖，注册必要路由；503需由实际探针决定 |
| BP-02 | 官方四页 PDF 有文本层，应提取文本并留页码 | `parse_pdf_text_layer` 返回 unparseable/scanned；独立 pypdf 读取4页3967字符。`parsers.py:104` 仅找 `TEXTLAYER:` 行 | R04 用成熟 PDF 提取器，增加真实文本层与扫描页分立回归 |
| BP-03 | 留档官方 NVD `vulnerabilities[0]` 直接含cve，应保留CVSS | 原结构报 `missing vulnerability wrapper`；人为加包装后 scores仍空；原分值9.6位于cvssData.baseScore。`nvd.py:32/58` 读取错误层级 | R04 修复入口形状及指标嵌套；留档hash `1bc5449375788cf417662cf3187bcd11c1484ed0b15026d4cf71760edd352c1f`。本轮未新增live NVD请求 |
| BP-04 | 真实模型调用应有generate/embed/rerank实现 | clients模块只有五个验证/策略函数与 FixtureProvider；三个模块入口均不存在；providers.yaml 全部not_configured | R05 实现已授权提供者；这是代码缺失，同时存在凭据阻塞，不能只归因于live |
| BP-05 | 发布事实及outbox应为PG事务，重启可查 | ClaimsLedger发布返回transactional:true；同实例1条，新实例0条。`claims.py:45/90` 是字典/列表操作，未调用SQL事务 | R02 增加真实repository/事务并保留历史；不能用返回布尔值证明事务 |
| BP-06 | 页内唯一条目保存失败且无持久化补偿，不应推进游标 | persist callback False，committed_count0，live_cursor仍由before-page变after-failed-page；失败ID仅在内存，新实例cursor为空。`scheduler.py:73/95` 失败continue后无条件推进 | R03 在PG事务中保存原文或可恢复失败任务后推进，重启/补采负例必须跑真库 |
| BP-07 | 同一用户目录的新认证服务应能读取有效会话和审计 | 新服务拒绝旧token，审计1→0；`authentication.py:194-196` 存在会话/尝试/审计三个内存容器 | R02 增加跨进程后端；用户目录持久化不等于会话与审计持久化 |
| BP-08 | 前端应可登录并查看来源/证据等 | frontend/src只有3文件；App仍显示“后端 API 未连接”，没有业务调用 | R01最小认证入口，R04逐链路页面，R17完整工作台；1条组件测试不能证明产品可操作 |
| BP-09 | 注入既有认证服务后，写请求缺Origin/CSRF应拒绝 | 登录200；随后不带Origin或CSRF的 `POST /auth/logout` 仍200。`auth_routes.py:96` 未调用 `validate_write_request` | 已证实路由安全缺陷；R01装配时与R20回归处理。最小修复为接入现有写请求校验并测试缺/错/正确值 |

BP-01至BP-08复核确认旧主要问题仍存在。BP-09是本轮新增可复现缺陷，已通知主控。发现时间由行为日志确定：BP-01至BP-08为20:50:51–20:50:52，BP-09为20:52:49–20:52:50。全部状态为未解决，本委派不实施修复。严重性均阻断相应真实链路验收；不会因153项测试通过关闭。

另确认 `jobs.py:32` 的queued/retry_wait均可直接认领，schema无next_retry_at，`complete_job:90`仅校验owner，未校验到期时间。这两项为源码证据和真库缺测，未冒充真库复现；R03需要隔离PG时钟/竞争测试。Compose当前只有PG/Redis/OpenSearch；没有API/worker/scheduler/frontend或新图/向量服务编排。dev.py只有unit/integration/security scope实现；这两个工程缺口来自源文件核查。

## 3. 实际入口与调用链

```mermaid
flowchart LR
  ENTRY[默认 app] --> FACTORY[create_application]
  FACTORY --> HEALTH[health live/ready]
  FACTORY -. 参数未注入 .-> AUTH[认证 router / session service]
  ADMIN[管理 CLI] --> ENGINE[build_engine]
  ENGINE --> USER[PG 用户目录]
  TESTS[离线测试调用] --> PURE[来源归一化 / PDF解析 / 游标 / ClaimsLedger]
  PURE -. 未装配 .-> ENTRY
```

在生产源目录范围，新 CBM 图中 `commit_page_persisted`、`normalize_nvd_record`、`publish_claims` 入向调用均0；publish_claims出向仅list.append与dict.get。rg同时确认这些函数在源侧无业务调用而测试侧有调用；图没有边本身不能独立证明绝无运行路径。create_application静态出向图能看到条件式build_auth_router，但实际默认OpenAPI404证明该边未激活。数据库build_engine实际调用位于管理CLI，不能当默认API/worker已装配。

## 4. 资源事实

| 资源 | 当前实测与日志 | 后续影响 |
|---|---|---|
| Python/uv | 系统3.13.11；uv0.10.9；项目锁定离线环境3.12.13 | 可运行既有后端；未修改系统版本 |
| Node/npm | 24.13.1 / 11.8.0 | 前端既有骨架测试可运行 |
| Docker | CLI29.2.0、Compose5.0.2；20:45:03首次查询管道不存在；20:48:50起docker version120秒超时124；20:52:51再查20秒超时124 | 本轮真容器/PG等integration blocked；不能据进程存在声称引擎ready |
| Docker进程 | 20:50:51观察到Docker Desktop/com.docker.backend进程；本委派未启动 | 资源在主控/外部启动中；R01需再次限时验证真正ready |
| WSL/CBM | Ubuntu-22.04可用；旧portable `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 0.11.0可执行 | 真实help、索引、schema/architecture/trace均已运行 |
| 模型/FOFA/数据库变量 | Process/User/Machine三域与OPENAI/ANTHROPIC/MODEL/LLM/FOFA/NVD/REDIS/DATABASE/PG/OPENSEARCH/QDRANT/NEO4J匹配的名称集合均空 | 只能说明本轮受检环境无候选引用；秘密管理器未核查，不能断言用户从未提供。R05/R08需提供者与安全注入引用 |
| 其他进程 | 观察到redis-server；无连接/协议测试 | 不宣称Redis integration通过 |

产品外部调用本轮0次，费用为0；Codex编程会话成本unknown。模型、FOFA、授权资产、人工金标及决赛模板未做live/人工探测，不读取附件秘密以消除阻塞。

## 5. codebase-memory-mcp 索引证据

索引项目：`dianzi-recovery-baseline-probe-8e265dc`；范围 `/mnt/d/dianzi/backend/src`，47个Python源文件；来源tree为上文 `b04281...`，文件hash另存 [indexed_source_hashes.json](../../runs/recovery_baseline_probe_20261014/indexed_source_hashes.json)。仅索引生产源码，未索引附件、秘密、holdout或用户资料。缓存指定工作区外 `/tmp/dianzi-cbm-recovery-baseline-probe`，persistence=false，未提交工具缓存或改全局ACL/库/配置。

真实命令 `cli --json index_repository --repo-path /mnt/d/dianzi/backend/src --name dianzi-recovery-baseline-probe-8e265dc --mode fast --persistence false`，成功516节点、1920边、0未索引文件；schema与architecture成功。`get_graph_schema`、`trace_path`参数先读取真实help。第一次 `trace_path --function-name ClaimsLedger.publish_claims` 退出1/function not found，依工具返回指引调用search_graph定位，再用 `--function-name publish_claims` 成功；失败日志保留，不把失败查询写成成功。索引没有覆盖主控项目名。

## 6. 实际验证与命令

所有命令的完整argv、cwd、开始/结束、退出码在 [commands.json](../../runs/recovery_baseline_probe_20261014/commands.json)。原始工具时间全部由实际系统时钟读取，日志使用Asia/Shanghai并带+08:00。本轮没有产品源码修复，不重复运行与此只读工作无关的全仓静态检查。

| 命令/范围 | 结果 | 证明边界 |
|---|---|---|
| backend：`uv run --locked --offline python ../reports/runs/recovery_baseline_probe_20261014/behavior_probes.py` | 两次退出0；9组最终观察；每次<2秒 | 探针成功执行，被测缺陷仍在；不是产品通过 |
| 根目录：`python -c`使用pypdf读取competition_brief.pdf | 退出0；4页3967字符 | 有真实文本层；未检验PDF版式或赛事文义 |
| backend：`uv run --locked --offline pytest tests/unit tests/contract tests/security tests/integration/test_t16_incremental_monitoring.py tests/integration/test_t21_claims_entities_conflicts.py --ignore=tests/contract/test_t07_jobs_outbox.py --no-cov -p no:cacheprovider -q -ra` | 退出0，153 passed、0 failed、0 skipped，1个Starlette/httpx弃用warning；20:50:52–20:50:55 | 47unit+72contract+20security+14两份内存模拟integration；未运行真实PG和固定DSN破坏性测试 |
| 同范围 `--collect-only -q` | 退出0；153项，分层见 [test_layer_counts.json](../../runs/recovery_baseline_probe_20261014/test_layer_counts.json) | 计数，不另计153次业务测试 |
| frontend：`cmd /c npm run test -- --run` | 退出0；1 passed，0 failed/skip；20:50:55–20:50:58 | 骨架组件测试；browser业务e2e not_run |
| WSL CBM index/schema/architecture/四条trace | 除首次错误方法名退出1外全部退出0；修正查询成功 | 只证明静态源码关系，不证明运行链路 |
| Docker版本2次有界重新查询 | 124/超时，未ready | 环境阻塞，不算业务失败或通过 |

分层状态：unit=passed（当前选择47）；contract=passed（当前选择72）；security=failed（已有20测试通过但新增BP-09路由负例失败）；真实integration=blocked（尚未运行，14内存模拟仅offline passed）；frontend=passed（仅1骨架组件测试）；e2e=not_run；live=not_run；manual=not_run。frontend组件层passed不代表页面业务链通过。未执行的性能、持续采集、重启/备份恢复、OpenSearch/向量/图真实集成、真实生成、人工金标不写passed。

一条人工读取命令曾误用backend工作目录却保留backend路径前缀而退出1，已在仓库根目录重新读取；属于定位命令错误，不是业务测试失败。没有吞掉该错误、改测试分母或将失败转skip。pytest使用--no-cov/no:cacheprovider和PYTHONDONTWRITEBYTECODE以免改变共享checkout的覆盖率与缓存。

## 7. 合同偏差、评分证据与下一步

本工作包没有修改合同，不对CR-R01–R09签生效；它为R00状态纠偏提供真实证据。需要按切片保留已有纯函数/PG原文/jobs基础，不因这些缺陷平行重写仓库，也不能把用户当前费用授权仍记成“没有预算”。

E1证据为默认装配与持久化缺口，F1为NVD/PDF/游标缺口，F2为账本/模型缺口，F3为模型/前端缺口；没有新正式评分结果。最小下一步：主控完成R00变更/映射与新独立审查；R01修默认装配、隔离测试与认证写边界，并真实核验引擎；R02补持久化；R03补PG任务/游标；R04补真实解析；R05以安全注入的真实产品API完成模型链。来源适配器与标注工具的纯内部准备可在真实前置满足后继续，不能越过相应live阶段门。

明确未检查：秘密管理器、真实付费接口、真PG/Redis/OpenSearch/向量/图、浏览器业务e2e、人工金标、正式性能与持续运行。核心风险：旧153项离线全绿与旧accepted均不能支持这些产品能力；本报告仅完成只读基线复核，需要主控的R00独立审核及后续真实修复验收。

## 8. 修订记录

| 时间 | 修改人 | 原因与证据 |
|---|---|---|
| {ended} | baseline_runtime_probe | 首次落盘；实际9组行为、153/1测试、资源与独立CBM结果 |
"""
    ended = datetime.now(local_zone).isoformat(timespec="seconds")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.format(started=started, ended=ended), encoding="utf-8")
    print(str(target))
    print(ended)


if __name__ == "__main__":
    main()
