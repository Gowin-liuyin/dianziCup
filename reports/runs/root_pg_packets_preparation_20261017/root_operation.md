# Root PG 逐窗操作

本包状态 `prepared_not_run`；只有 Root 可执行以下真实 PG 命令。准备者未读取 DPAPI、DSN、token 或主机环境，未连接数据库。Root 当前基线 `0291d197587141b9f7f5da0d01800d8cbdf58d11`。先确认 Source 当前 requested/effective 两 OID、实际 parent/Root/Source PID 与完整出生身份及 PG 窗口已分配；准备清单不证明正在运行的 Source 身份。

固定预算为 48s child / 58s controller / 60s outer；2 target + 1 parent sampler 最多 3；512MiB/process、1GiB/job、2 logical CPU、native9 + outer1 = full Windows10。真实父角色若是 superuser，连接限制只证明观测峰值，不能声称硬连接 cap。Source OID `10451302` / `10434264` 仅用来核身份前后相同，不连接或修改其数据库。

执行入口采用已观察的 bundled PowerShell 绝对路径；不使用 nestedCommand、shell eval 或重新拼 shell 字符串。每个命令只含一个白名单标签。完成一窗、核 cleanup 与自有出生残留 0、释放采样连接后，再运行下一窗。不要并行。

```powershell
C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe -NoLogo -NoProfile -File D:/dianzi/reports/runs/root_pg_packets_preparation_20261017/launch_root_pg_packet.ps1 -Packet D:/wt/r18-qa-reader-review1-closed-pairs/reports/runs/r18_trusted_qa_reader_review1_closed_pairs_20261017/pg_support_closed_pairs/root_launch_packet.json -Group qa_reader_closed_pairs_pg_1
```

QA 固定 source `07664fd7f328803ade6f30372bfd04c395033a42`，workflow witness `e310b1a8f5a47a8e7f409805d034472b1f8a4306`。同一 packet 依次使用 `qa_reader_closed_pairs_pg_2` 至 `_7`；数量依次为 3、3、3、3、3、3、1，合计 19 不同原节点。不得把旧 QA source 的 PG 结果移签此版本。

```powershell
C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe -NoLogo -NoProfile -File D:/dianzi/reports/runs/root_pg_packets_preparation_20261017/launch_root_pg_packet.ps1 -Packet D:/wt/r10-policy-review1-fix1/reports/runs/r10_policy_review1_fix1_20261017/pg_support/root_launch_packet.json -Group pg_policy_original4
```

R10 固定 source `986b01ea21b9cc51d5bd30bd569a8fc63af0d3ba`。4 个原 policy 节点使用 synthetic GraphStore，只证明真实 PG 持久化/图工作策略；不证明 Neo4j、模型或来源 live。其已有 material 标记 `pending_author_fix1_material` 原值保留；准入依赖实际 raw hash，不把该标记虚构成已知提交 SHA。

```powershell
C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe -NoLogo -NoProfile -File D:/dianzi/reports/runs/root_pg_packets_preparation_20261017/launch_root_pg_packet.ps1 -Packet D:/dianzi/reports/runs/root_pg_packets_preparation_20261017/r16_pg_support/root_launch_packet.json -Group pg_history_original13
```

R16 固定 backend source `14ce965b66fbf8f74221eb01e1426cf1636ea9fc`、UI `dd35f7a90bb8573e2acbd62319a62577804fcddd`；material `f2c5ad7229d4ce04e95e4457466731319120285e`。精确选择原 HTTP PG12 + reviewer mode PG1，不能再加入另一个 author modes PG1 或计成14。原 `history_engine` 在 nonce DB 中创建自己的 `test_r16_change_http_<uuid>` schema，执行原迁移，finally DropSchema；controller 初始 nonce schema 单独迁移到 0031，无 R05 seed。nonce DB 使用成熟母板指定的现有授权 test role，不新建或修改角色。

helper 每次首先校验 frozen packet 路径、schema、组白名单、所有 controller/admission/entry/source 的 raw SHA 与精确 mtime，以及 Root 31 个迁移。任一改变都停止，不用旧 packet 签新源码。之后仅由 Root 在内存解密原 DPAPI reference，清空子进程环境后注入允许项；DSN 不在命令参数或报告中。UTC 授权到期为新鲜当前时间 +600s；controller 重新检查剩余时间。

controller 保留成熟母板的 9 字段 nonce marker、数据库/schema OID 与 owner/comment 完整身份、birth-aware 子进程终止、采样、0连接清理与 Source 两 OID 的前后比较。成功须读取 controller 原始 `.command.json`、XML、`.samples.json`、migration/pytest raw logs，核 0fail/error/skip、预定不同节点数、时间、内存CPU、target≤2/total≤3、own DB0、target0/sampler0/ownbirth0。outer launch exit0 本身不是完整证明。

outer 收据写到本目录的 `root_launch_<Group>_*`；controller 收据保留各固定 support 路径。已有收据拒绝覆盖。若失败，保留原失败字节，在新有界修复材料与新 execution 路径中复核；不要重写金标、断言、阈值或计分分母。没有真实执行的 PG/live/manual 仍记 not_run；工具语法/哈希校验不算产品 unit 数量。

冻结 helper raw SHA256 `2cb1c7b05d7f077f9efff443f68df7659875e3ac0ed876307f66090e082a53ef`；mapping raw SHA256 `852217ca0703f76fbe01f8a69799bbc51d2428a20ca54129883f726582142d9a`。本包 `bounded_prepare.ps1` 是已保留的历史首次准备运行，不供 Root 重新生成；Root 使用上面的固定 launch helper。
