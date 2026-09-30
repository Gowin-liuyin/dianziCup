# RV-FIX-T02 · T02 核心项独立复查（收窄范围版）

- 复查对象：T02（项目骨架、依赖锁定与质量命令），实现者=主控工程 Agent，状态 awaiting_review
- 复查者：独立复查 Agent（RV-FIX-T02，接替长期未交付的 R-T02；本文件不覆盖 R-T02.md 命名空间）
- 复查范围：**核心 5 项**（验收断言真实性抽查、三组命令复跑、锁文件真实性、冻结未动、诚实性）。全量深审未做，未查项见 §5，如实记 not_run。
- 复查性质：只读验证 + 仓外临时探针；**未修改仓库任何文件**（仅写入本报告与 RV-FIX-T02_runs.log）；未装依赖、无 git 操作、未更新 progress/。
- 复跑时间：本机 23:26—23:32 前后（vitest 自报 Start at 23:26:51；日期以本机时钟为准，未采信报告内 2026-09-30 字样作为复跑时间）。

## 0. 复查对象 SHA-256（本轮回跑前后未改动）

| 文件 | SHA-256 |
|---|---|
| docs/tasks/T02_project_skeleton.md | 9e0321d0330f986aafa77bee8924be1e7820e60e8cc82bb7e9945a5b1b91b108 |
| backend/tests/unit/test_t02_project_skeleton.py | e3dfe6b302905a28deb0233e03bb5f600df78dfca107db56a1f90e32267e6416 |
| backend/pyproject.toml | eadfce5b24877a9d595fd52c0006fbeff83a31428a08b26bf16124f9052fff27 |
| backend/uv.lock | 376092d327ee66a07de500cdedd3a244777c843a387b321cb80b43124b3b126d |
| frontend/package-lock.json | 2adcf1caaa702fa0b37e7b7df278da4cf52574eee67c6e913296cc23ae2a9afd |
| frontend/src/App.tsx | 44dd3b4b0dbdc2c5015a7d1771663b20ccade3d8d82cc127bd7f6a518ad6a021 |
| frontend/src/App.test.tsx | f8ebd565ee62556d9e58cd9ff0a03b4417eacbfda922e2a8c3f76f6dfe41c4e2 |
| scripts/dev.py | 63318a2de16f7b066da7cedbb869a83067f68547296dc0e77ba64e130e6f1564 |
| README.md | 3aa7df0b4c62ff9e6d322ffb6d8f8dbb5cd635d39e92bd3cb5103f2ed000af96 |
| reports/tasks/T02.md | 7c385a7f4b0e4144512a1409c18991b2ee005eac3c9c016067a0327bf705b80d |
| contracts/baselines/plan_baseline_t01.json | 0e01e776d3f7c8174f0a2938d5e1d8e97cac6af607007e92bb60a29a60cb7ba0 |

## 1. 命令复跑表（本轮回跑实测，原始摘录见 RV-FIX-T02_runs.log）

| # | 命令 | 工作目录 | 退出码 | 测试数/失败/跳过 | 摘要 |
|---|---|---|---|---|---|
| a1 | `uv run pytest tests/unit -v` | D:\dianzi\backend | **0** | **9 / 0 / 0** | 9 passed, 1 warning（StarletteDeprecationWarning）；覆盖率 100%（17 语句，门槛 60%） |
| a2 | `uv run ruff check .` | D:\dianzi\backend | **0** | — | All checks passed! |
| a3 | `uv run ruff format --check .` | D:\dianzi\backend | **0** | — | 6 files already formatted |
| a4 | `uv run mypy src` | D:\dianzi\backend | **0** | — | Success: no issues found in 5 source files |
| b1 | `npm run lint` | D:\dianzi\frontend | **0** | — | eslint . 无告警 |
| b2 | `npm run typecheck` | D:\dianzi\frontend | **0** | — | tsc --noEmit 无输出 |
| b3 | `npm run test` | D:\dianzi\frontend | **0** | **1 / 0 / 0** | ✓ src/App.test.tsx（vitest v3.2.7） |
| b4 | `npm run build` | D:\dianzi\frontend | **0** | — | vite v6.4.3，26 modules，built in 463ms |
| c1 | `E:\miniconda\python.exe scripts/dev.py check --scope unit` | D:\dianzi | **0**（期望 0） | 9 / 0 / 0 | 透传 pytest，9 passed |
| c2 | `E:\miniconda\python.exe scripts/dev.py check --scope integration` | D:\dianzi | **3**（期望 3） | — | stderr: `ERROR not_implemented: integration`；stdout 无 PASS |
| c3 | `E:\miniconda\python.exe scripts/dev.py check --scope bogus` | D:\dianzi | **2**（期望 2） | — | argparse: invalid choice: 'bogus' |
| d1 | `python scripts/verify_plan.py --root D:\dianzi` | D:\dianzi | **0** | — | PLAN_OK（中文控制台输出为 GBK 乱码，PLAN_OK 前缀可辨） |
| d2 | `python scripts/verify_plan.py --root D:\dianzi --baseline contracts/baselines/plan_baseline_t01.json` | D:\dianzi | **0** | — | PLAN_OK |
| e1 | 仓外探针：temp 副本注入类型错误后 mypy（见 §2.1 C03） | %TEMP%（仓库外） | **1** | — | `Argument 1 to "add_numbers" has incompatible type "str"` [arg-type] |
| e2 | 仓外探针：temp 副本无错误 mypy | %TEMP%（仓库外） | **0** | — | Success: no issues found in 7 source files |

工具版本（本轮回跑实测）：Python 3.12.13（backend/.venv）、pytest 8.4.2、node v24.13.1 / npm 11.8.0、vitest v3.2.7、vite v6.4.3；dev.py 由 E:\miniconda\python.exe **3.13.11** 驱动（与任务卡指定命令一致，dev.py 仅用标准库，与项目 3.12 约束不冲突）。

## 2. 五项判定

### 2.1 验收断言真实性抽查（T02-C01—C06 vs 任务卡 §5）—— 判定：**有条件通过（存在 2 项覆盖缺口）**

逐案核对 `backend/tests/unit/test_t02_project_skeleton.py`（9 项）与 `frontend/src/App.test.tsx`（1 项）。**未发现伪造测试**：9 项均有真实输入与可观察断言，无“只测没报错”，无把实现输出抄作期望（`application.title`、`requires-python` 属固定合同值断言，可接受）。**未发现期望值由被测实现动态生成**。

| 案例 | 测试/证据 | 断言是否真实可观察 | 判定 |
|---|---|---|---|
| C01 干净安装/可导入/测试数>0 | `test_lockfile_exists_for_clean_environment_install`（仅静态存在性）＋ 主控命令批 | 部分：锁存在性是真实断言；「按锁干净安装」在测试内无断言，报告已如实记 `uv sync --locked` 成功实测 not_run。本轮回跑佐证：API 可导入（pytest 装配 TestClient 通过）、前端 build=0、测试数 9+1>0 | **部分缺口（普通）** |
| C02 错误版本→明确不兼容 | `test_pyproject_pins_python_312_and_keeps_type_checks_enabled` | 静态合同断言（`requires-python = ">=3.12,<3.13"`、`disallow_untyped_defs = true`）真实但为配置字符串核对，**无“错误版本被拒”的行为负例**（报告已如实记 not_run）。其中 `assert "mypy" in pyproject_text` 过弱（任意提及即过），建议收紧为 mypy 配置段断言 | **部分缺口（普通）** |
| C03 故意类型错误→非零 | 测试文件内**无对应用例**；仅配置断言 + 报告引用前端 TS2688 类比 | 缺口：任务卡 §5 要求每案“实际输入与可观察断言”，C03 未固化为测试。**行为本身为真**（本轮回跑仓外探针 e1/e2：注入 arg-type 错误 mypy 退出 1，干净副本退出 0） | **覆盖缺口（普通），行为已实证** |
| C04 未实现 scope 非零且无 PASS | `test_unimplemented_integration_scope_exits_nonzero_without_pass`（子进程实跑） | 真实：断言 returncode==3、stderr 含 not_implemented、stdout 无 PASS。本轮回跑 c2 独立复现一致 | **通过** |
| C05 缺配置→清楚错误/不联网/不泄密 | `test_application_import_does_not_open_network_connections`（socket.connect 抛错桩）、`test_source_files_contain_no_secret_values` | 真实：联网禁令是行为断言；密钥扫描是真实正则扫描（范围 scripts/ + backend/src，本复查看到范围偏窄，见 §2.5）。「缺必须配置→清楚配置错误」的行为断言**缺失**，现以 `/health/ready` 503 not_ready 代替（诚实但非原案语义） | **部分缺口（普通/建议）** |
| C06 前端无 API 数据→未连接、无假统计 | `frontend/src/App.test.tsx` + 人工核读 App.tsx | 真实：断言 connection-status 含「未连接」且数字型业务统计正则命中为 null；App.tsx 仅有标题+未连接提示，确无统计。负例正则 `\d+[\s]*(次|条|个|%)` 偏窄（纯数字/英文单位不命中），当前无统计故无实际逃逸 | **通过（1 项建议）** |

附注：后端 `test_health_ready_reports_not_ready_without_external_dependencies` 的 docstring 标注“T02-C06 对应”，实际语义更贴近 C05/就绪诚实性，属标注错位（建议级）。dev.py 未实现 scope 的核心要求（真非零且无 PASS）**已确认**：integration 退出 3、stderr 明示 not_implemented、stdout 无 PASS 字样。

### 2.2 三组命令复跑 —— 判定：**通过**

三组全部按任务卡命令复跑，退出码与期望一致（表 1 a/b/c 行）。后端 9 passed、前端 1 passed，ruff/format/mypy 全 0，dev.py 0/3/2 与退出码合同吻合。与 T02 报告 §4 声称的最终态一致，未发现“报告写通过、复跑失败”情形。

### 2.3 锁文件真实性 —— 判定：**通过（工具生成可信）**

- `backend/uv.lock`：47,709 B；头为 `version = 1` / `revision = 3` / `requires-python = "==3.12.*"`（uv 生成器标记）；33 个 `[[package]]`（含 editable 根包 ai-intel-backend），33 name、34 version、134 处 url/hash 行，`source = { editable = "." }`、`wheels/sdist` 结构完整——符合 uv 真实锁文件结构，**非手写**。
- `frontend/package-lock.json`：177,770 B；`lockfileVersion: 3`、name=ai-intel-workbench、packages 358 项、其中 347 项带 integrity+resolved、354 项带 version，integrity 为标准 npm sha512 指纹（如 node_modules/@babel/core）——npm 生成器产物特征完整，**非手写**。
- **记录不一致（普通）**：T02 报告两处记 `package-lock.json` **206324B**（§1.2、§4 行 18），实测当前文件 **177,770 B**。时间线可解释（vitest ^3.0.5 升级后 npm install 重生成锁文件，报告保留了早期尺寸），但报告未更新该数字，属证据数字与终态产物不符，建议修正为终态尺寸/哈希。

### 2.4 冻结未动 —— 判定：**通过**

`verify_plan.py --root D:\dianzi` 与 `--baseline contracts/baselines/plan_baseline_t01.json` 两次均退出码 **0**、输出 **PLAN_OK**（附带“不代表产品测试通过”的自声明，符合 G0 口径）。未见冻结文件漂移迹象。

### 2.5 诚实性 —— 判定：**通过（无夸大，not_run 如实）**

- **密钥**：仓库文本全量扫描（sk-/AKIA/PEM/GitHub PAT/bearer/赋值型密钥共 6 类模式，覆盖 .py/.ts/.tsx/.js/.json/.md/.yml/.toml/.txt/.html/.css 等，排除 node_modules/.git/dist/.venv）**0 命中**；无 .env 文件入库；`config/dev.env.example` 仅占位值（`dev-only-not-a-secret`）。与测试内扫描结论一致。
- **前端无假业务统计**：App.tsx 显式「后端 API 未连接（开发骨架阶段）」，无任何数字统计/示例数据；Vitest 断言负例正则为 null。**通过**。
- **README**：明确“开发骨架阶段”“无任何业务能力与指标”“CI 尚未实际运行（not_run）”，已可运行/待实现命令分表登记，未夸大。**通过**。
- **报告 T02.md**：not_run 清单如实（uv sync --locked 成功实测、C02/C03 负向实测、npm audit、CI 运行、容器/live 均登记 not_run 或 blocked）；§3 缺陷 4 项含修复与复验过程、非零退出全部归因；§3.3 主动申报 vitest 主版本升级需补变更记录；§3.1 RUF001/002/003 豁免标注范围与理由并“待 R-T02 审查确认”；§7 完整继承 G0 §7 五项限制声明（PLAN_OK≠产品测试通过、blocked_live 不抹去、合成案例待复核、独立审查≠人工审批、遗留项不改变）。**通过**。唯一事实性瑕疵见 §2.3 锁文件尺寸。
- 关于 RUF001/002/003 ignore：属定点豁免（仅歧义 Unicode 三规则，为中文 docstring 标点），报告已写明范围与理由，符合 AGENTS.md“新增忽略规则必须有明确范围并在审查记录说明”。**接受**；建议后续改为 per-file-ignores 或仅对 docstring 生效，收窄面（建议级）。

## 3. 问题分级

### 阻断（blocker）：**无**

未发现伪造测试、密钥泄露、verify_plan 非 PLAN_OK。

### 普通（应修，建议在 T02 收口/阶段检查前关闭）

1. **P1 · C03 无故障注入测试**：任务卡 §5 要求每案有实际输入与可观察断言，`test_t02_project_skeleton.py` 缺 C03 用例。行为已由本轮回跑实证（注入 arg-type → mypy 退出 1；干净 → 0），补一条 temp 目录注入用例即可闭合。
2. **P2 · `uv sync --locked` 成功实测缺失**（C01 缺口）：报告自报 not_run；本次复查受“不装依赖”约束亦未执行。需主控在 backend/ 下补跑留证。
3. **P3 · 报告锁文件尺寸数字与终态不符**：206324B vs 实测 177,770 B，建议修正或注明系 vitest 升级前版本。

### 建议（不阻断）

4. C02 负例补实测（错误版本解释器安装被拒），并把 `assert "mypy" in pyproject_text` 收紧为 mypy 配置段断言。
5. C05「缺必须配置→清楚配置错误」补行为断言（现以 /health/ready 503 代替，语义偏移）。
6. C06 负例正则加宽（纯数字、英文单位），防止未来统计逃逸；修正 ready 测试 docstring 的 C06 标注错位。
7. RUF001/002/003 豁免改 per-file-ignores 收窄；vitest 主版本升级补一条变更记录（报告 §3.3 已自报）。
8. secret 扫描测试的范围建议扩到 frontend/src 与 config/（当前仅 scripts/ + backend/src）。

## 4. 结论

**建议 accepted（附条件）**：核心 5 项中命令复跑（2.2）、锁文件真实性（2.3）、冻结未动（2.4）、诚实性（2.5）**全部通过**；验收断言真实性（2.1）**有条件通过**——既有 10 项测试断言全部真实、可独立复现，无伪造、无夸大，但 C03 未固化测试、C01 的干净安装未留证。

**接受条件（关闭前建议不进入 T02 最终 accepted/阶段检查）**：
1. 修复 P1：补 C03 mypy 故障注入测试（可断言非零退出与错误内容）。
2. 修复 P2：补跑 `cd backend && uv sync --locked` 并留日志。
3. 修复 P3：修正报告中 package-lock.json 尺寸记载。

若项目口径要求 §5 六案**全部**固化为自动化测试（而非允许负向案例以独立复跑补证），则 P1 由条件升为必须修复项，结论相应为 **needs_changes**；按报告 §5 已声明的“负向实测待独立审查复跑补证”口径，本次复查已提供 C03 行为实证，故取“accepted 附条件”。

**升级判定：不升级**。三项升级触发条件（伪造测试 / 密钥泄露 / verify_plan 非 PLAN_OK）均未触发。

## 5. 未查项（not_run，本收窄复查不做）

- 全量深审：代码风格逐条、架构合理性、测试覆盖完备性矩阵、CI 内容逐行审校——not_run。
- `npm audit` 明细/依赖漏洞处置——not_run（未装依赖、不改文件约束）。
- `uv sync --locked`（安装类，按指令不装依赖）——not_run（见 P2）。
- C02 错误版本负向实测（需另一版本解释器）——not_run。
- 容器构建/集成/live/性能、CI 实际触发、git 状态与提交检查——not_run。
- R-T02_runs.log 的逐条内容审阅——not_run（仅确认存在，前一审查者未产出 R-T02.md）。

---
*RV-FIX-T02 · 只读复查；未修改仓库文件、未装依赖、无 git 操作。原始命令摘录见 RV-FIX-T02_runs.log。*
