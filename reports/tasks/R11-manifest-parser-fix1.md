# R11 / T24 · 清单候选解析初审两项 Must 修复

状态：`awaiting_review`；实现：`complete`（仅两项修复及纯候选准备切片）。unit=`passed`（101直接用例），contract/security=`passed`（保留原1/32限定场景）；原独立38探针整体仍`failed`（37通过、1未确认CSV方言探针失败）。integration/frontend/e2e/live/manual、全工程fullsuite=`not_run`。不自行关闭独立Must、不签整R11/T24/G-D，无push、无accepted。

记录时间：2026-10-16T02:43:32.386+08:00。工作树`D:/dianzi-wt-r11-manifest-parser`，分支`codex/r11-manifest-parser`；修复基线`e651a0576785de4d8f9bf4e0dd114c8984bfd2d3`；代码冻结`64dcd946601cd0e0f7435f59019ee709e3738a35`。所有正式修复检查都在该代码SHA运行；预冻结green收据的HEAD仍为e651，其工作树源码已修改，不作为固定SHA通过证据。

## 审查输入与先红

已读AGENTS、00执行索引、12/R11、T24、03/04/05合同与冻结progress，复核当前分支和调用方；继续按Ponytail full 5.2.0限制为最小修复。独立审查报告为`D:/wt/r11-review1/reports/reviews/recovery/G-D-R11-manifest-parser-review-1.md`。源review artifact_manifest本体SHA256逐字节核实为`1c644e365aaf9bf1d5ad9a273f0c85da669f3609162b51cad6cbfc980051c0e0`。

独立38探针原文件完整复制到新run，原bytes SHA256为`ac13a06334ea163e5c3f95da0d7592aaa7c61a232b1ed7178be6b99983ab2b1c`，复制前按源review manifest长度/hash核实。没有改其输入、expected或skip，也未格式化这个冻结原件。基线先红为34 passed / 4 failed / 0 error / 0 skip：权限换序、UTC转换溢出、tzinfo无实际偏移三个Must红例，以及一个非Must的未确认CSV方言探针。

本次另加36个直接单元场景：权限集合的全部6种排列、同scope原bytes重放、未知None与显式空、大小写及前后空格身份保持、有序dependency_path不可混排；observed_at/recorded_at两入口的无偏移、下/上UTC溢出、非法偏移、偏移读取错误、None/string/bool/int/object类型，以及真实+08、合法UTC极值和偏移仅读一次。原源码先红为13 passed / 23 failed；失败包含原错误类型/字段定位不完整的可观察边界，原red日志和JUnit保留。

## 最小修复与文件

- `backend/src/ai_intel/assets/manifest_parser.py`：只在semantic_value对非None tool_permissions排序。返回候选tuple和原bytes仍保留来源顺序；None与空集合继续不同。不trim、不coerce权限身份，不改变其他有序字段。
- 同模块新增私有`_require_utc_timestamp`供observed_at、recorded_at全部时间入口共用：拒绝非datetime、tzinfo缺失、实际utcoffset=None；读取一次明确偏移，再用标准库固定偏移timezone转UTC，避免第二次不稳定偏移落回宿主时区。ValueError/OverflowError/TypeError归一为`invalid_timestamp`，缺偏移为`timezone_required`，定位分别为`/observed_at`和`/recorded_at`，不回显异常值。不填当前时间、不截断、不clamp。候选使用已归一时间，不在构造时再次转换。
- `backend/tests/unit/test_r11_manifest_parser_identity_time.py`：新增36直接用例；原65的三个源码文件、原112场景均未修改。
- `reports/runs/recovery_r11_manifest_parser_fix1_20261016/`与本报告：原38副本、先红/固定复跑、CBM、旧证据离线核验及新材料manifest。
- `.gitattributes`：仅为此唯一新run追加`-text`及既有raw日志空白属性；材料首次diff check揭示两个先红stdout及对应JUnit含pytest原始尾空白，另仅对这四个精确原始材料追加`-diff`保留bytes，不修剪失败输出。不改旧run精确属性、公共合同或全局检查策略。配置文件自身的Git blob归一与工作副本hash分别记录。

没有修改domain（包括其既有时间值对象）、auth、schema、依赖/lock、PG/API、settings、worker、frontend、root progress、旧报告或旧run。当前代码没有产品调用方，READ_ASSET的纯候选范围、PG实际asset归属/写权限缺口保持。没有建立内存DB或第二事实源。

## 固定SHA真实命令与结果

解释器为既有`D:/dianzi/backend/.venv/Scripts/python.exe`；pytest/质量cwd为本树backend，PYTHONPATH仅对子进程指向本树src。`python`在下表中表示该已记录绝对解释器。完整命令、+08开始/结束、退出码和SHA在新run同名JSON；原日志未修剪。`--no-cov`是定向检查，不代表全工程覆盖率门通过。

| 收据 | 实际命令核心 | 结果 |
|---|---|---|
| review_38_red | `python -m pytest ../reports/runs/…/test_independent_manifest_review.py --no-cov -q --junitxml=…` | 基线e651，exit1；34 passed / 4 failed |
| added_boundaries_red | `python -m pytest tests/unit/test_r11_manifest_parser_identity_time.py --no-cov -q --junitxml=…` | 基线e651，exit1；13 passed / 23 failed |
| fixed_direct_101 | 原unit/contract/security三文件与新增identity_time文件，`--no-cov -q --junitxml=…` | 代码64dcd946，exit0；原65+新增36=101 passed，0 fail/error/skip |
| fixed_related_112 | t04_domain_contracts、t06_access_scope_boundaries、t18_model_clients、r08_aggregate_connectors、r13_fofa_relay，`--no-cov -q --junitxml=…` | 同SHA，exit0；112 passed，0 fail/error/skip |
| fixed_original_review_38 | 未修改38原件，完整`--no-cov -q --junitxml=…` | 同SHA，exit1；37 passed / 1 failed，0 error/skip；三Must红例均转通过，CSV仍红 |
| fixed_mypy | `python -m mypy src/ai_intel` | exit0；100源文件通过 |
| fixed_ruff | `python -m ruff check` 本片源码及四个直接测试文件 | exit0；通过 |
| fixed_format | `python -m ruff format --check` 同五文件 | exit0；5文件已格式化 |
| fixed_diff | `git diff --check e651a05… HEAD` | exit0；代码及新增直接测试通过 |
| fixed_preserved_evidence | `python ../reports/runs/…/verify_preserved_evidence.py` | exit0；旧manifest本体、102件旧冻结Git blob、原run/report/65测试源码与gzip保持 |

不把独立38说成全部通过。剩余输入为`Name,Ver\nlangchain,1"2\n`：标准库csv.reader的当前方言接受此未引用字段中的引号，候选version仍为来源字符串`1"2`。独立探针期待更严格规则，但当前合同未冻结RFC 4180或该规则，原review与主控均明确它不是Must。没有为绿新增自造CSV解析器，也没有删例、改期望或skip；若未来明确更严格方言，须另行冻结合法/非法配对和兼容性范围。版本字符串的生态有效性仍交版本判断模块，本解析器不声称其有效或安全。

未运行全工程fullsuite，未修其旧限额问题；本片101、相关112与38的分母均保留，不汇成正式评测准确率。秘密、路径/命令、身份伪造、大小/组件/深度上限等原65及独立38场景继续实际复跑；Windows大参数的显式ids与原10MiB payload未变。

## CBM与证据完整性

修改前显式assets目录CBM为107节点/390边；冻结64dcd946后实际刷新为108节点/394边、5源码文件，not_indexed/parse_partial/parse_unusable均0。独立XDG缓存为`/tmp/dianzi-r11-manifest-parser-fix1-cbm`，官方portable 0.11.0 CLI仅做本地源分析。schema与trace保留：parse_manifest产品入向0、出向22；私有时间helper只有parse_manifest这1个调用函数，源码rg核实两个调用点和唯一UTC转换点。没有从图推断PG/API生产链路已接通。

旧e651的evidence_manifest本体仍为`e1827675743d736036c0d6ded14ce3243280ef96dd694033a431253066d30a92`，102件原材料逐原Git blob核对；旧run、旧报告、原65测试源码工作副本均无差异。原parser源代码历史blob仍保留，当前仅有上述有界修复；不将旧源码hash冒充新代码hash。

原41,951,937B失败日志gzip仍为44,590B / SHA256 `6a03747311af06c0812c21743004c3cc046ac1a2f62dd9b60f004e0ce759cad6`，分块解压长度/hash仍为41,951,937B / `3cccbce776d43c2fb1910a851859ae70de0d3290a387efbd870814e78d8b0323`。旧压缩/原件均未移动或重写，没有打印巨行或巨大参数；这轮没有停止进程。

新材料manifest记录review本体hash、原probe复制hash、代码SHA、每件材料表示法/长度/hash与原证据验证结果；材料封存后逐Git blob核验。没有追认初审38绿、没有修改旧102证据。

## 未完成与交接

网络、模型、付费任务、服务启动、PG操作、实际资产访问/扫描均0；全部输入为显式合成unit/contract/security或原独立review fixtures。FOFA授权范围仍缺，SBOM、PG幂等/current/实际tenant归属、正式写权限、四态/产品真值、OpenVEX与UI仍未在此片完成，评分F2/F3/P2只有纯候选代码局部证据。

交原独立reviewer对冻结新代码及材料定向复核两项Must，保留未确认CSV观察；仅root依据复跑与审查登记状态。修复作者不自签关闭Must或整R11/T24/G-D。下一步仍由root完成正式接线与原卡验收。
