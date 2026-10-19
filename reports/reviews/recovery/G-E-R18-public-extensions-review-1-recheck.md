# G-E / R18 public extensions 定向复核 1

What this change does: 新冻结代码将 TaskDescriptor.poll_uri 收紧为 UUID 的 8-4-4-4-12 分组，新增四个负例和一个合法正例。原 v2、14 个复制定义和此前23例没有改变。

任务与意见：R18 public 合同切片 **有限 Ship**；原审查 Must1 在此新 SHA 关闭。没有登记 accepted，不放行整 R18/G-E、runtime producer、8000token控制或原 T04/T32/T35/T51 整卡。

被审 SHA：`831c61f5c82d663434172a258bbd0c85757a6567`；基线 `456320b6c78e2936fd9f9767724ec3eb17f5c88b`，父提交正是该基线。fresh WT `D:/wt/r18-public-extensions-review1-fix1`，分支 `codex/r18-public-extensions-review1-fix1`，创建完成 `2026-10-16T09:49:37.1235927+08:00`。reviewer `/root/r18_public_extensions_first_independent_review`，沿用原非作者身份。复核证据截止 `2026-10-16T09:50:56.224741+08:00`；报告首次写作与封存时间在 manifest.json，使用 +08:00。

本轮仅审两个变更文件：`contracts/schemas/public_api_extensions_v1.json` 与 `backend/tests/contract/test_r18_task_poll_uri.py`，32新增/1删除。重读执行地图、恢复R18和固定进度，原引用合同/旧调用链在此两文件修复中未改变，原审查的能力边界仍适用。采用已读取的 Ponytail 5.2 review。本次只新增本报告与 `reports/runs/recovery_r18_public_extensions_review1_fix1_20261016/`，不改业务、合同、旧报告/日志、进度或盲测，不提交/push。

Must1 核验：schema 第1456行实际冻结内容为 `^/api/v1/tasks/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`。原触发输入（合法 task_id，poll_uri 尾部为36个 `-` 或36个 `a`）均被拒绝；错误分组与追加 `/extra` 也拒绝，合法UUID路径保留。未发现新的 Must/Should。

此前97例脚本从封存初审目录复制，输入、断言、整个文件均保持字节相同：SHA256 `3f31471ff54297733111160f248219580bdb91c7c0fdd3913de94f21a058527b`，与初审 manifest 匹配。本次脚本按自身位置读取**新 WT 的冻结实际 schema**，没有修改内存 schema、没有启用原建议验证插件。此前95通过/2失败，现在同97例全部通过。

真实命令完整 argv、cwd、+08 起止、退出码与原输出见同目录 `commands.json`、各 `*.command.json`、JUnit与stdout/stderr。测试工作目录是新 WT/backend，使用 `D:/dianzi/backend/.venv/Scripts/python.exe`；offline runner 显式阻止 socket.connect。

| 检查 | +08 开始 / 结束 | exit | 结果 |
|---|---|---:|---|
| pytest 原23+新5，`-c pyproject.toml -v --no-cov -p no:cacheprovider --junitxml=...` | 09:50:25.079937 / 09:50:28.100180 | 0 | 28 passed，0fail/skip |
| pytest 原样97，参数同上、直接读取冻结 schema | 09:50:25.123424 / 09:50:27.504647 | 0 | 97 passed，0fail/skip |
| check_fixed_scope.py | 09:50:25.208773 / 09:50:26.892050 | 0 | JSON Schema元合同通过，14defs相同，原v2/原23测试Git blob相同，schema结构仅新pattern改变 |
| Ruff check 两个合同测试 | 09:50:52.466576 / 09:50:52.631979 | 0 | 通过 |
| Ruff format --check 两个合同测试 | 09:50:52.789907 / 09:50:52.989302 | 0 | 2文件格式通过 |
| mypy `--config-file pyproject.toml` 两个合同测试 | 09:50:53.139690 / 09:50:56.224741 | 0 | 2 source files无问题 |
| git diff --check `456320b 831c61f` | 09:50:52.545332 / 09:50:52.613472 | 0 | 通过 |

`--no-cov` 仅用于隔离合同检查；完整全仓60%覆盖门未运行、未撤销、未降门槛。两runner网络连接尝试0，本轮物理PG请求0、付费调用0、下载0。主控提到的早先测试 import/错误mypy配置失败保留在其原runtime草稿日志；本轮未读取或复核那些未提交runtime材料，不将其测试数或结果合入本报告。

准确新 schema SHA256：Git blob与LF文本均 `4ccc4337586137a407359a1c4a59dc5d92081a2f4b50ee32cc53fac16095d50b`；本WT CRLF字节为 `008bd7b0999222514f28685bab1c330a324a05c166838a6d669b6b3c78d56aec`。831版本CR-R18第10行仍写初审旧摘要 `af28...`，任务报告也仍引用原23数量；主控已说明正在补材料，须更新为新Git/LF摘要与此次复验版本。这是版本材料待同步，不伪称新代码缺陷，也没有审查未冻结的新文档。

原审查中的安全语义限制完整保留：格式引用不证明支持，同事件/current/ACL/规则/资产快照资格、跨数组与真实输入范围、安全Citation URI、source实际健康、poll UUID与task_id相同、partial真实进度、游标授权/epoch绑定仍需producer/typed validator。旧v2默认兼容，新媒体类型必须显式opt-in；不允许JSONSchema绿后直接推导CLI0/1或“安全”。本修复没有增加生产调用链，backend/src未变，不把初审CBM图或本轮测试当runtime接线证明。

未检查：完整unit/integration/security/frontend/e2e/live/manual、真实PG/HTTP/客户端、输出8000tokens/1MiB分页、词表缺失/损坏行为、插件隔离、并发与费用；这些维持not_run。评分证据只支持A1/E1/X1的public版本合同与该格式缺陷修复，未取得性能/准确率/全客户端兼容或整R18验收证据。

Verdict: **Ship，仅831c61f的public合同切片及Must1修复。** 主控可按新摘要同步材料，随后在旧14defs不变、显式opt-in和共享PG/认证/证据资格核验的条件下继续producer/SDK/MCP实施；新runtime链必须另冻结、另审查。本报告与所有自有证据由manifest封存，初审失败日志不改，不自签accepted。
