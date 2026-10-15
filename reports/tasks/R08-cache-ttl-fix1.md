# R08 · cache 剩余整秒 TTL 修复 1

状态：awaiting_review；修复 implementation=complete，原 R08 整包仍 partial，0019 生产迁移/产品接线未验证。主控明确授权修复独立审查发现的半秒缓存剩余期偏差；作者不 accepted、不 spawn、不 merge/push。

工作区 `D:/wt/r08-cache-ttl-fix1`，分支 `codex/r08-cache-ttl-fix1`；基线 `6706cd9eeae8bae612fc7e86dff2e2b0416eeaef`。代码提交 `4a3ba0f384eb15cc64b2e4e9cde33805909c6884`，tree `79cbc8e8c3c82ef25b5371d89d9f7f33aeac2010`；材料清单见 [artifact_manifest.json](../runs/recovery_r08_cache_ttl_fix1_20261016/artifact_manifest.json)。原冻结 worktree、reviewer probe、旧报告和所有原 raw 日志未修改；reviewer 原负例 hash 由主控另行封存，不冒认作者复测。

输入/输出：年龄 86399.5 秒的已持久 safe total，PG 尚有 0.5 秒有效期；旧公式 `86400-int(age)` 产生 TTL=1，超过剩余期。新公式对 retrieval 与 nullable observed 两条时间分别计算 `floor(86400-age)` 后取最小，剩余整秒 <=0 沿用不写 cache 分支。年龄 86399 秒仍可写 1 秒，86399.5 秒不写，86400 秒仍 stale/无当前值；PG 尚未过期的半秒值保持原 available 语义，未知观察时间仍 unknown。

改动仅为 `backend/src/ai_intel/assets/aggregate_service.py` 的 stdlib `math.floor` import 和两处计算顺序；新增 unit `test_r08_cache_ttl_fix1.py`、PG `test_r08_cache_ttl_fix1_pg.py`，以及 [CR 补充](../../docs/decisions/CR-R08_aggregate_persistence.md)、本报告/独有 run 材料。没有修改全局 86400 秒 TTL、指标阈值/分母、现有 tests/gold、adapter、domain、repository/table、migration、schema、API、worker、publisher、frontend、lock 或 progress。Ponytail 5.2 full 继续生效：直接复用 Python 标准库 floor，不添加自定义舍入层、依赖或缓存实现。

先核对 AGENTS、00、12 R08、冻结 CR 和 task_state；真实 `rg` 找到 `_result` 是唯一 `_cache` 调用方。先新增边界测试、在未修业务实现上运行自有 red，结果 2 failed/8 passed、exit 1：retrieval 与 observed 的 86399.5 秒输入均错误写 TTL=1。原始 [unit_red.log](../runs/recovery_r08_cache_ttl_fix1_20261016/unit_red.log)和 unit_red.xml 保留。这是业务断言失败，没有改期望值或把失败 skip。

修复后实际检查如下；完整 argv/cwd/开始结束 +08 时间/退出码在 [commands.jsonl](../runs/recovery_r08_cache_ttl_fix1_20261016/commands.jsonl)：

| 检查 | 实际命令 | 结果 |
| --- | --- | --- |
| 自有 red | `python -m pytest tests/unit/test_r08_cache_ttl_fix1.py --no-cov -q` | 2 failed/8 passed；exit 1；unit_red.log/xml |
| 自有 green | 同文件 | 10 passed；exit 0；unit_green.log/xml |
| 必要原相关回归 | `python -m pytest tests/unit/test_r08_cache_ttl_fix1.py tests/unit/test_r08_aggregate_service.py --no-cov -q` | 31 passed：新 10、原 service 21；exit 0；targeted_units.log/xml |
| 真实隔离 PG | `python reports/runs/recovery_r08_cache_ttl_fix1_20261016/execute_pg.py`，内部仅新 PG 文件 | 10 passed；exit 0；pg_final.log / pg.xml |
| Ruff / format | 仅改动 service + 两个新测试文件 | passed，3 files formatted；exit 0；ruff.log / format.log |
| Mypy | `python -m mypy src/ai_intel/assets/aggregate_service.py` | 0 errors in 1 source file；exit 0；mypy.log |

最终 41 项定向检查（新增 20 + 必要原相关 21），0 failure/error/skip。原实现的 320 项历史检查没有重跑，不作为该新 SHA 背书。初次新测试排版的 Ruff 提示经 formatter 修正；最终检查没有忽略规则。源码/tests/CR 定向 diff check 通过；新 run `.gitattributes * -text` 只保存原 Windows 日志 CR/LF 字节，文件按 manifest 核 hash，不改写旧 red evidence。

测试覆盖两条时间的 86399/86399.5/86400 秒、future retrieval 不显示当前且不写 cache、future observed 被类型边界拒绝、PG 已提交的真实 UUID/hash/safe total 被 cache setter 独立读回、cache failure 不损害已提交零总量、最新 PG failed 不读取旧值 cache、fixture 不碰 live cache/调用身份。所有 service adapter 都是明确无网络的合成 fixture；其中 live 仅测试模式标签，不是假称真实在线供应商。新 provider/account/model 请求为 0，实际费用仍 unknown。

PG 从主控获准 WSL test-services/connection.json 在进程内捕获；未输出 DSN/密码，未放 argv。只创建本 fix1 独有 `test_dianzi_r08_cache_ttl_fix1_20261016`，loopback:25432，迁移到既有 0016 后 create 原冻结自有表/触发器。没有改原 R08 测试库、dev 或生产库，没有 downgrade/delete。准备 receipt 明确不是生产迁移验收，测试库保留。

CBM 本机官方 0.11.0 独立 src/asset 索引：src 1409 nodes/7128 edges，默认排除 assets；assets 基线 120/464，修复后 120/463。`_cache` trace 指向 freshness/安全 payload/缓存 Protocol，caller 为 `_result`，再到 read/collect；结合实际 rg 与 3 行业务 diff 核对。缓存只在仓外 `/tmp/r08-ttl-fix1-{src,assets}-cbm-20261016`，没有索引报告、秘密或 holdout；manifest 绑定代码 commit/tree。

合同偏差已按主控授权修复，不变更 TTL/阈值/评分。评分证据限于 F2/X1 的时效与缓存边界、P2 的可复现回归；不证明指纹准确率、资产数量或正式评分目标。未运行：生产 0019、真实 Redis IO、新 live、API/worker/publisher/frontend/e2e/manual、全仓性能/覆盖率。下一步由原独立 reviewer 定向复核此新代码和材料，主控唯一登记/merge/push；作者此处停止。
