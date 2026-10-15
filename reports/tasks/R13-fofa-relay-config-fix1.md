# R13 / T08 / T25 · falsey fixture 网关隔离修复

状态：`awaiting_review`；本修复实现 `complete`。unit/contract/security 为 `passed`，integration/frontend/e2e/manual 为 `not_run`；本轮 live `not_run`，授权资产 live 仍 `blocked_scope`。记录时间：2026-10-16T00:28:12+08:00（Asia/Shanghai）。作者不能登记 accepted，整 R13/T25/T42 未完成。

工作树：`D:/wt/r13-fofa-relay-config`；分支：`codex/r13-fofa-relay-config`。接收 HEAD 为 `bde7497b3b67b96da0af63e85b197931858a8ca7`，原业务为 `35a91e2644075238825724c2f3d7bbab83f30cde`；本修复业务冻结为 `2e1f5029a8e153bdd8289ac20b67e50d51e30bca`。本轮开始时工作树干净；保护主仓与其他包的修改。

## 范围、输入输出与根因

已读 AGENTS、00 执行图、11/12 恢复合同 R13、03/04/05/07 合同、T08/T25/T27、当前状态和交接、原作者报告及上一评审保留证据。当前进度 R13 仍 pending/not_started；这是独立候选配置包的修复，不能替主控改公共进度。按当前授权，仅修复评审已实证的 P1：合法网关实现 `__bool__() -> False`，且显式 fixture_mode=True 时，原配对校验通过，但 `fixture_gateway or create_network_gateway(...)` 忽略该对象、构造真实网关；探测结果仍可能标 synthetic。

输入为已校验配置、非 None 的 RelayGateway 和显式 fixture 标志；输出必须由同一注入对象取得，真实工厂零调用，固定账户路径单次调用、重定向 0，返回仍标 `is_synthetic=True`。已有未配对 flag/gateway 两个拒绝测试、truthy 正常 fixture、HTTP/运输错误合同、凭据目标及既有网络策略继续通过。

仅修改两个业务/直接测试文件：

- `backend/src/ai_intel/assets/fofa_relay.py`
- `backend/tests/contract/test_r13_fofa_relay_account_wire.py`

另新增本报告和 `reports/runs/recovery_r13_fofa_relay_config_fix1_20261016/`。未修改公共 settings、API、worker、PG、网络实现、契约/依赖锁、示例配置、进度、金标、阈值或分母。原作者报告、原 run 和上一评审 raw 未覆盖。`protected_paths_unchanged` 对接收 HEAD 的只读 diff 退出 0；最后交付 manifest 记录实际 Git blob 字节。

修复只把网关选择改为 `if fixture_gateway is not None` 分支，直接复用原注入对象；else 中原 NetworkPolicy、OriginCredentials 和并发参数未变。回归继承现有 FixtureGateway，加一个 falsey 行为；真实工厂被 monkeypatch 为调用即失败的 Mock，检查零调用、替身收到唯一固定请求、已知额度与 synthetic 标记。没有新增工厂、包装层、配置选项或依赖。

## 调用方与索引证据

修改前建立独立 CBM 0.11.0 assets-root fast 索引，缓存 `/tmp/dianzi-cbm-r13-relay-fix1-20261016`、persistence=false，37 nodes/85 edges；冻结代码重建为 37/84，not_indexed/partial/unusable 均 0。默认 src 索引排除 assets，因此本轮没有用它宣称完整覆盖；仅索引该模块，不包含测试、报告、秘密、holdout。前后 `FofaRelayClient.__init__` trace 与修改前 `probe_account` trace 保存在新 run，图中 0 callers 只代表这个窄根。导入的公共网络实现不在本图范围，源码/rg 交叉确认其调用，而不是凭图判行为。

源码 rg 的产品调用方仍为 0，未见 settings/runtime/API 接线；直接调用存在于 R13 contract/security 测试，以及原 run 的历史受控 `probe_account_once.py:24`。本轮仅读该脚本命中行，未执行它。历史脚本不注入 fixture；此次选择分支保留其非 fixture 创建路径。独立只读协助仅定位调用方和测试位置，没有改代码或充当最终 reviewer。

## 真实验证

新 run 每条 `<label>.json` 含完整 argv、cwd、真实 +08:00 起止时间、exit、HEAD 和日志 SHA256；对应 log/XML 保留原字节。Python 复用原仓外 venv：`D:/dianzi-runtime-cache/r13-fofa-relay-config/venv/Scripts/python.exe`；显式 PYTHONPATH 指向本 WT/backend/src，import_origin_before 已核实实际导入路径。没有安装依赖。

pytest 均为 `python -m pytest <下列路径> --no-cov -q -p no:cacheprovider --junitxml <本 run 对应 XML>`；`--no-cov` 仅用于授权定向检查，不更改既有全仓 60% 覆盖率门，本轮该全仓门未执行。业务验证时间为 00:24:05–00:27:09，固定提交时间为 00:27:23。

| label / 实际测试路径 | 结果 | exit |
|---|---|---:|
| reviewer_probe_red：原评审 raw/test_independent_relay_boundaries.py::test_explicit_fixture_mode_never_constructs_real_gateway_even_for_falsey_fixture | 修复前 1 failed；真实工厂调用断言失败 | 1 |
| regression_red：tests/contract/test_r13_fofa_relay_account_wire.py::test_falsey_fixture_gateway_never_constructs_real_gateway | 新回归修复前 1 failed；真实工厂 Mock 被调用 | 1 |
| unit：tests/unit/test_r13_fofa_relay.py | 38 passed，0 failed/errors/skip | 0 |
| contract、contract_final：tests/contract/test_r13_fofa_relay_account_wire.py | 各 14 passed；包括新回归；不重复累计 | 0 |
| security：tests/security/test_r13_fofa_relay_boundaries.py | 12 passed，0 failed/errors/skip | 0 |
| reviewer_probe_green：与 reviewer_probe_red 同一单例 | 1 passed，原 probe 文件未改 | 0 |
| network_regressions：test_r03_network_gateway、test_r03_network_review_regressions、test_r03_doh_resolver 三个 unit；test_t08_network_and_sources、test_r03_network_transport 两个 security；test_t08_network_redirects contract | 138 passed，0 failed/errors/skip | 0 |

原 R13 63 例加新回归为 64；加网络回归共 202 个不同仓内用例通过。原 reviewer 最小单例另算 1，不能算新的独立评审。保留上一审查的原 1 failed/14 passed 和本轮红日志，不替换失败结果。

静态实际命令：`python -m ruff check` 与 `python -m ruff format --check` 均覆盖原四个 R13 产品/测试文件；`python -m mypy src/ai_intel/assets/fofa_relay.py`。初始 ruff/format 各 exit 1，仅新增额度断言长 101 字符；原日志保留，断言换行后 ruff_final/format_final 均 exit 0（4 files already formatted），mypy exit 0（1 source file 无问题）。`git diff --check` 业务文件 exit 0；Git 提示 LF 将转 CRLF，为工具提示。自有 run 的 `.gitattributes` 仅对 log/JSON/XML 设 `-text` 以保留精确字节，没有改根规则或忽略检查。

## 未跑层、合同偏差、评分证据与交接

integration/frontend/e2e/manual 均 not_run：没有 PG、服务接线或 UI 改动。本轮没有全仓 unit/CPU 门、性能、连续运行或模型测评；当前授权明确限于定向回归。未读取 DPAPI 或任何秘密，新增文档/账户/资产请求均 0，模型/扫描/PoC 执行均 0；原 2/2 账户预算已用尽，不发第三次。此前账户只读证据与资产 live 缺口继续由原报告记录，本修复没有新的外部可用性结论。

没有改变公共合同或计划验收条件；改动仅恢复原 fixture 隔离语义，现有网关复用比新增防护包装更小。E1 仅新增“合法 falsey 替身不进入真实网关”的实测边界证据；不据此签 F2/P2 资产定位、观察时间、漏洞确认、R13/T25/T42 或最终 live。

下一步：主控派全新、未参与实现的 reviewer 核对冻结业务 SHA、原失败和本轮 manifest/测试；评审后由主控唯一登记/集成。作者只交 awaiting_review，本包不 push、不自行 accepted。
