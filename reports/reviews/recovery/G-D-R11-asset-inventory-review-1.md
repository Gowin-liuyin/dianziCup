# G-D / R11 / T24 · 私有资产 PG 与独立 router 切片首次独立审查

记录时间：2026-10-16T04:34:09+08:00。审查人：`/root/r11_asset_inventory_first_independent_review`，非作者，新首次独立审查。审查材料与报告供主控登记；未自行写 `accepted`。整 R11、T24、G-D 均未在本审查签收。

这次改动实现资产身份、current 指针、不可变历史及导入收据的 PostgreSQL 持久化，并提供复用现有认证的独立 HTTP 工厂。审查意见仅限已批准的 CR-R11 资产 PG/router 切片：指定 206 项回归与额外 8 项独立探针通过，未发现必须先修复的阻断缺陷；有一项 P3 非阻断查询债务。默认覆盖率门仍失败，生产迁移和产品接线仍未验收。

## 冻结与改动边界

- 实际首 cwd 为 `D:/dianzi`；检查了分支、工作树、`git worktree list`，主仓已有大量未提交修改，本审查未碰。确认目标路径/分支未占用后，自行执行 `git worktree add -b codex/r11-inventory-review1 D:/wt/r11-inventory-review1 bc8798cf5efc81e210a429884930ca545af43ad8`，exit 0。之后只在该独立 worktree 工作。
- 作者 worktree：`D:/wt/r11-asset-inventory`。冻结代码 `6f82c68075dde808da9c92e3a49ad2e605e6b5a8`，代码 tree `29f219d204bedf33af03828346f583a39ea81912`；三表提案 `4b15c77`；最终材料 `bc8798cf5efc81e210a429884930ca545af43ad8`，材料 tree `a0157ea735fcad96b5fd1558ca3f362f3bf7c53d`。
- 最终材料相对代码冻结没有 source/tests/migrations/lock/public schema 变化。manifest 的 9 个源码、测试、CR Git blob 证明逐项匹配代码与材料版本。`git diff --check 6f82c68 HEAD` exit 0。
- 已读 AGENTS、00、12/R11、T24 全部实施项与 C01–C06、03/04/05/06、冻结状态和交接、已批准 CR-R09、CR-R11_asset_inventory、public v2，以及 Ponytail 插件 5.2 review。审查中文按本轮明确要求，不采用技能的默认英文输出。
- 本轮只新增此报告及 `reports/runs/recovery_r11_asset_inventory_review1_20261016/` 下的审查脚本、日志、JUnit、收据、manifest；venv 与过滤后的源码索引副本位于自有临时目录。未改业务代码、旧测试、schema、迁移、依赖、状态；未 commit/push/spawn。

## 材料原字节核验

权威 manifest 路径为 `reports/runs/recovery_r11_asset_inventory_20261016/artifact_manifest.json`。从 Git blob 读取的本体 SHA-256 为 `d453b93dde90abe18d4241bf4a55d778d689110b20625d36d10bf1c13a171c0e`，与指定值吻合。独立核验全部 94 个 gzip Git blob 的长度/hash，并解压核对 93 条原证据的长度/hash，全部一致；见 [archive_verification.json](../../runs/recovery_r11_asset_inventory_review1_20261016/archive_verification.json)。压缩 blob hash、解压 raw hash、源码 Git blob hash分别记录，未把 Git 换行过滤后的 JSON 视图当原运行字节。

旧材料 `429f432` 的 12 个 commands/database JSON 换行过滤不一致和三份 CBM 视图 EOF 空行红字仍在旧 gzip 与旧 manifest 中。独立读取 `material_fix_diagnosis.json.gz` 及 `material_initial_diff_check.log.gz`，确认旧 diff 检查 exit 2、12 条原字节不一致的真实记录；它们不算最终材料通过证据。未覆盖作者未跟踪 raw，不强行改换行；本轮核验使用 `bc8798c` 中解压后正确的 gzip。

## 实际环境、命令与结果

离线执行 `C:/Users/yinha/.local/bin/uv.exe sync --frozen --offline --no-progress`，exit 0；CPython 3.12.13，自有 `backend/.venv`，未变锁文件。只将已授权 WSL Ubuntu-22.04/root 的 `/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json` 捕获到进程内存，校验原连接为 loopback、25432、test 库；无 DSN/口令输出或落盘，无 secret vault 访问。

唯一新库为 `test_dianzi_r11_inventory_review1_0b7b8b72729049`，真实 PG 16.14。04:27:05–04:27:06+08 前向升级至 `0016_source_response_receipts`，随后只显式 `metadata.create_all` 三张新资产表。该动作是 `create_tables_not_production_migration`；不是生产 `0018` 成功。未用 dev DSN、未 downgrade/drop 旧库。新测试库保留，见 [database_receipt.json](../../runs/recovery_r11_asset_inventory_review1_20261016/database_receipt.json)。本冻结版本不包含主控之后的 0017 富化 metadata 审查或 0018 冻结结果。

下表解释器均为 `D:/wt/r11-inventory-review1/backend/.venv/Scripts/python.exe`，测试 cwd 均为该 worktree 的 `backend`。完整 argv、cwd、+08 开始/结束、退出码在 [commands.json](../../runs/recovery_r11_asset_inventory_review1_20261016/commands.json)、[supplement_commands.json](../../runs/recovery_r11_asset_inventory_review1_20261016/supplement_commands.json) 与 [probe_recheck_commands.json](../../runs/recovery_r11_asset_inventory_review1_20261016/probe_recheck_commands.json)。`--no-cov` 定向回归没有改变原门。

| 检查 / 命令核心 | 实际 +08 窗口 | exit / 真实结果 |
|---|---|---|
| `-m pytest tests/unit/test_r11_inventory.py tests/contract/test_r11_inventory_contracts.py tests/security/test_r11_inventory_boundary.py --no-cov -q` | 04:27:06–04:27:12 | 0；26 passed，0 fail/error/skip |
| `-m pytest tests/integration/test_t24_asset_inventory.py --no-cov -q` | 04:27:12–04:27:19 | 0；46 passed，0 fail/error/skip |
| 原 parser、identity_time、candidate contract、parser boundary 四文件 `--no-cov -q` | 04:27:19–04:27:21 | 0；101 passed，0 fail/error/skip |
| domain/access/auth-state/auth-security/outbox 五文件 `--no-cov -q` 初次 | 04:27:21–04:27:24 | 1；26 passed、7 setup error、0 skip；自有 run_id 与库名不匹配 |
| 同五文件，修正本轮运行环境参数后的复验 | 04:29:23–04:29:36 | 0；33 passed，0 fail/error/skip |
| `-m ruff check` 四源码与四新增测试 | 04:27:24 | 0；All checks passed |
| `-m ruff format --check` 同八文件 | 04:27:24–04:27:25 | 0；8 files already formatted |
| `-m mypy src/ai_intel` | 04:27:25–04:27:34 | 0；111 source files 无问题 |
| 默认配置执行新 pure 三文件，不加 `--no-cov` | 04:27:34–04:27:40 | 1；26 case passed，但整体覆盖 23.57% < 原 60% 门 |
| 自有 `review_probes.py --no-cov -q` | 04:29:36–04:29:38 | 0；8 passed，0 fail/error/skip |
| 自有探针整理 imports/format 后复验 | 见独立命令收据 | 0；8 passed，0 fail/error/skip；不重复计入总数 |

成功指定回归的独立 case 总数是 `26 + 46 + 101 + 33 = 206`；额外独立 8 项使本轮唯一成功用例数为 214。初次 setup error、默认覆盖门失败和重复复验不从历史消失，也不重复增加通过数。覆盖率未降门，未运行完整工程覆盖率门；该定向覆盖率失败不能登记成工程全绿。

本轮独立运行程序最初的 run_id 少了 `review1_`，触发 `scripts/dev.py:60` 的精确隔离 guard。只以真实新库名反推正确 run_id，未修改 guard/fixture/源测试；复验 33 项通过，原 log/XML 保持。最初建立日志目录的 PowerShell cwd 相对路径失误导致 uv 尚未执行，工具输出已保留在会话；仅移动自有空目录后离线同步成功，不以最初 shell 打出的 0 当安装证据。自有审查工具的初次 Ruff imports 红字也保留，修复范围仅新脚本，最终 Ruff 通过。

自有证据封存脚本初次错误地把“旧全部 raw 视图变化”也断言为 12，exit 1；实际是 12 个 JSON 过滤差异，加上在材料修复时发生正常版本变化的 `seal_evidence.py`。只收窄自有断言到具体 JSON 过滤证据并保留 13 个全部变化记录；最终 94 gzip/93 raw 的严格 hash 断言没有放宽。此为审查工具期待范围错误，不是业务或最终原字节核验失败。

## 合同、行为与 T24 六案例

| 案例 | 独立检查及可观察结果 |
|---|---|
| C01 合法 JSON/CSV | 同 asset 的相同业务 canonical hash/快照复用；JSON 与 CSV 原字节 hash 各由服务器计算，当前 snapshot 私有 PG 保留首次 raw，不把第二次同当前导入变成新历史。schema DTO 与 Component 五公开字段投影合同通过。 |
| C02 重复导入 | tenant+actor+route+key 收据隔离；同 key 同请求返回原 snapshot，即使有 B 版本也不退回 A current；参数/raw/mapping 不同 409。重复当前仅新增请求收据，不新增 change/epoch/job/outbox。独立补测两 actor×两 route 相同 key、同当前四次重导入，只有四条收据增长。 |
| C03 新旧版本 | A→B→A 产生 1/2/3 历史与前驱，current 最后版本；并发相同请求一次提交、并发不同内容同 key 一次成功一次冲突、并发更新线性历史。current/previous/receipt 复合 FK 防跨 asset/tenant，snapshot UPDATE/DELETE trigger 与 commit current 非空约束实测拒绝。 |
| C04 未知完整性/配置 | 缺组件保持 unknown，缺权限/渠道/网络值保持 None；不输出排除或安全结论。额外空组件清单实测保持 unknown；本切片没有实现四态自查，不能据此称四态已通过。 |
| C05 非法 CSV/限额 | 实际 10001 行、非法列、私有路径、1 MiB+1 拒绝，无部分事实。独立 HTTP 二进制 JSON 恰好 1048576 bytes 成功，额外 1 byte 得 413；PG 长度/raw hash吻合，拒绝后全部计数不变。 |
| C06 私有边界 | 租户来自现有服务器认证；伪 body tenant/role/path 拒绝，无权限先 403，不可见与不存在统一 404。原文仅 PG BYTEA，GET DTO无 raw/path/DSN，没有下载路由或公共 trace 原文输出。 |

`inventory_routes.py:82–92` 在同业务事务重新锁定 session/user 与当前权限，写要求 WRITE_ASSET；没有给 analyst 自行授权。现有 CSRF/Origin 机制复用，撤销前/角色改变前请求拒绝；原 46 项及独立撤销竞争实测：持 auth 共享锁的写提交先完成，撤销事务随后完成，后续读/写均 401。

真实 HTTP SQL 观测顺序是 auth FOR SHARE → tenant advisory → asset advisory → assets FOR UPDATE → publication advisory → scope epoch 写；原集成测试又以第二事务持 asset 行锁并取 scope publication 锁验证不反转。不根据纯静态排序宣称并发已验。直接服务没有内部 commit。额外探针在 `save_change_publication` 已写完 epoch/change/job/outbox/publication receipt 后注入失败，确认全部回滚且 current 保持旧版；成功调用后调用者主动 rollback 也无残留。业务真值在 PG，没有缓存/内存成功替身。

资产改名以 `inventory.py:224–225` 的 typed `AssetNameConflictError` 及 HTTP 409 明确拒绝，无 snapshot/receipt/change 副作用。本切片未实现 rename 操作。列表按不变 created_at+asset_id，历史按 snapshot_number 倒序；current 更新与新历史加入不重复旧页，游标绑定 tenant/asset/product。额外替换 langchain 为 llama-index 后，product 过滤只查 current，原历史仍可读取。

## 调用链与未完成边界

官方 WSL CBM 0.11.0 对排除缓存的独立源码副本建索引：src 1409 nodes/7128 edges，assets 154 nodes/603 edges，architecture/schema已读。src 的 fast 模式明确排除 `ai_intel/assets`，因此另建 assets 索引，不能以 src 图没有节点下业务结论。最初两次少模块名的 trace 返回 function not found/exit 1，原输出保留；用 search_graph 得到精确 qualified 名，再执行 assets `inventory.InventoryService.import_manifest` 与 `inventory_routes.build_inventory_router` 的 trace，exit 0；见 cbm_* 与 [cbm_recheck_commands.json](../../runs/recovery_r11_asset_inventory_review1_20261016/cbm_recheck_commands.json)。图没有解析出路由 lambda 到服务的全部调用边，因此同时 rg 实际源码核查。

实际 `api/app.py:118–135` 没有 include 资产 router；`workers/runtime.py:98` 的 handler 注册表没有资产变化重判 handler。独立 FastAPI/TestClient 挂载可用和 outbox 入库不等于主应用/worker闭环。以下均保持未完成：SBOM CycloneDX/SPDX adapter、主控唯一生产0018迁移、正式 API接线与异步 import任务协议、frontend/e2e、真实资产/manual、3→5 产品真值、四态研判/证据包/OpenVEX。本轮外部 HTTP/API/model 调用、第三方资产扫描及付费任务为 0，未读取 holdout 或秘密库。

05 旧表的 analyst 写权限与现有 ROLE_PERMISSIONS 仍矛盾；本切片按已批准 CR 要求 WRITE_ASSET，不算解决旧合同矛盾。`asset-imports` 是同步 201，不算满足旧 202 异步协议或 10 MiB/10000 长上传接线。public v2 当前确实没有 AssetSnapshot DTO：私有 DTO映射03完整字段，Component只做既有五字段投影；不能称已有完整 public v2 AssetSnapshot 兼容。

八层登记建议：unit/contract/integration/security 在本切片范围 passed；frontend/e2e/manual 为 not_run；live 为 not_run/blocked_live（本轮无真实外部/资产验收授权与输入）。生产迁移、应用接线、覆盖门不得由这四层的定向通过推成 passed。评分 F2/F3/P2 仅新增可追溯授权资产快照及边界证据，没有官方准确率、性能、3→5 产品或整项评分结论。

## 非阻断债务

1. **[P3] 历史分页多读 private raw BYTEA**（`backend/src/ai_intel/assets/inventory.py:417`）。该查询选择整张 snapshot 表，再只从 canonical_payload 构造响应。独立输入是已成功导入的 1 MiB 合成清单：观测 SELECT 包含 raw_input，响应仅 869 bytes 且不含 raw_input 字段，见 [history_projection_debt.json](../../runs/recovery_r11_asset_inventory_review1_20261016/history_projection_debt.json)。最小修复是仅选择 snapshot_number 与 canonical_payload；100 上限页会额外传输每个历史 raw，此为按限额推导的成本，不是已运行 100 MiB 性能基准。未修不会导致本次已测的响应原文泄露，但会浪费 DB传输和进程内存。本审查未改业务，修复复验 not_run；若后续修改投影，应重跑当前/历史/分页/raw不泄露回归。

Verdict：**Ship，仅限批准的资产 PG/独立 router 切片，带上述 P3 债务与覆盖门/未接线限制。** 主控可以凭冻结版本与真实日志登记切片；本报告不自行 accepted，不签整 R11/T24/G-D。下一步建议先由主控冻结唯一0018、解决权限/异步/public DTO兼容决策，再独立核验主应用与 worker 接线。Not checked：生产迁移、完整覆盖门、frontend/e2e/live/manual、SBOM、四态自查与产品真值。
