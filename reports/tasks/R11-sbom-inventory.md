# R11/T24 · SBOM真实库存接线与容量修复

状态：`awaiting_review`；本有界接线实现完成，独立review待主控。整个R11/T24/T28仍partial，生产0022/API app装配和SBOM界面不由此报告验收。未修改progress，未push，未accepted。

记录时间见run的 `report_write_receipt.json`（实际Asia/Shanghai到秒）。最早结构化命令记录为2026-10-16T06:09:31+08:00；此前读取/工具探索没有完整起止收据，不补写。

冻结代码：`0892b6af7fbc0c16651aeb25f14493fb4c3fa48d`。WT：`D:/wt/r11-sbom-inventory`；分支 `codex/r11-sbom-inventory`。基底 `5f32b90b1a34f2d4b6c7f11da10c32b470b55569`；先merge已审pure材料 `f6acedcd2b004671c317f55dd058f46e5e517de9`，然后cherry主控表合同 `0532c4f58611e068fc7d5b03da984bc57dbad9f2`（本WT `e1cad47f1c2f90bc024cd99c9b189613d675fb4c`）。无新依赖或主版本变动。

## 变动文件与实际行为

- `backend/src/ai_intel/assets/manifest_parser.py`：只调整库存JSON局部结构边界；共享模型JSON helper仍50000。重复键、非有限数、溢出float、UTF-8、代理码/NUL、深度16、10000组件与原字节大小门保持。正常输入的投影算法/摘要不改。
- `inventory.py`、`inventory_routes.py`、`inventory_contracts.py`：既有认证/Origin/CSRF/幂等/tenant/事务入口显式接受CDX/SPDX。新增独立sidecar GET。旧导入/列表/快照DTO字段保持完全相同。
- `sbom_inventory.py`、`sbom_inventory_contracts.py`：复用已审纯parser的dispatcher及typed冻结声明；不重写SBOM parser，不让checksum充当image_digest、图充当路径或complete声明充当安装范围完整。
- 新5个直属测试文件：unit容量/dispatcher、contract、security、真实PG；原SBOM unit/contract只修改主控批准的两条旧缺口预期，保留原输入、官方schema与fixture。
- `docs/decisions/CR-R11_sbom_inventory_proposal.md`、本报告及独立run。主控新增sidecar模型/CR另在0532，不由本作者修改。原inventory_models、auth、API app、knowledge、迁移、锁、公共schema、金标/holdout与progress不改。

输入仍是显式bytes：CycloneDX JSON 1.5/1.6/1.7、SPDX JSON wire SPDX-2.3。HTTP原文1..1048576字节；SBOM自身200000节点、深度16和10000组件门不变。没有路径/URL/XML读取、引用抓取、命令或PoC执行。READ_ASSET纯解析权限不代替WRITE_ASSET库存写权限。

## 原容量缺口与数学上界

原two-field CDX10000与name/purl/version高密度CDX10000原文未超过1MiB，却因投影50005/90005节点超旧50000而typed `projection_node_limit`。本次首红3例完整保存在 `capacity_red.log/xml`，6:09:31–6:09:38，exit1，3failed；随后原101 manifest回归加新3容量均通过，exit0/104passed。原公开dense fixture精确797858字节，raw SHA256 `5a524d5fdc2e9bebef8fafbaa1870080ffb7be896b561da3c11d35a611ffed4d`；本次直接复用原gzip，不重下、不改bytes。

共享helper不允许传超过50000的参数，不能仅换调用参数。因此局部使用成熟标准库json.loads加原有有界walk，预算按合同最大合法结构计算：顶层root及8字段键值17；10000组件各最多8字段键值、对象及64路径项，10000×81；两个64项声明数组128；4/3/2配置字段键值18。总 `810163` 节点，键也计数。新正例覆盖满8字段+64路径的10000组件（在parser原10MiB纯内存界内），另有1MiB内CDX两字段/多字段与SPDX name/versionInfo10000。不是只留name，不删组件或截断。

主控批准两条原缺口证明改为完整容量正例。修改之前实际执行的两个旧预期在新容量实现上得到 `DID NOT RAISE`，原 `original_sbom_capacity_before_update.log/xml` exit1/2failed保留；这是旧能力缺口预期与已修复行为的冲突，不能当为业务仍未修复，也不改成skip。执行期间按批准更新了磁盘测试文件，因此原traceback读取磁盘的新函数行文可能与XML中实际加载的旧函数名不同；该日志只证明旧预期不再成立，修复前业务失败证据来自capacity_red原日志。没有修改原input、schema、金标、门槛或分母。

## PG事实、历史和兼容

唯一raw存既有asset_snapshots.raw_input BYTEA，精确raw SHA由服务端计算。新 `asset_snapshot_sbom_sidecars` 写typed source/checksum/ref/dependency/composition/external-document及未映射字段位置，保存adapter/spec/projection/raw/全JSON/combined摘要和服务器认证的快照身份。opaque原值由不可变raw保留，不进入读取DTO。历史读取用冻结payload，实测替换parse_sbom为抛异常函数后仍能读取历史，证明未在读取时重解析。

同current判等：SBOM使用combined，JSON/CSV使用原projection。graph-only、checksum-only、composition-only、opaque-only变化各新建快照、推进current、epoch/change/outbox；原projection hash相同仍不吞变更。outbox旧manifest_sha256保持projection，同时仅SBOM附combined_semantic_sha256及sidecar_sha256。空格/对象键序改变combined相同可复用；精确raw不同复用同幂等key仍冲突。旧请求重放返回旧history，不恢复旧current。A→B→A形成3个编号与3个不同snapshot ID。

新sidecar表三列FK/immutable触发器真实PG拒绝跨tenant绑定、UPDATE/DELETE；发布失败回滚snapshot、sidecar、current和publication；4并发相同combined变化只发布一次。冻结payload shape/binding损坏返回503，错误响应不泄内容或tenant，不伪造默认成功。

`GET /assets/{asset_id}/snapshots/{snapshot_id}/sbom` 只读认证tenant，现行role在事务入口重新锁核；foreign统一404，analyst仅读，viewer无读。真实Origin/CSRF、匿名/失效会话、额外tenant参数、未知format、CSV mapping、路径文字、1MiB+1均拒绝，不写部分事实。旧GET/POST字段、分页、current及历史兼容有原46真实PG回归。

## 真实命令与结果

全部解释器为 `D:/wt/r11-sbom-inventory/backend/.venv/Scripts/python.exe`，cwd `D:/wt/r11-sbom-inventory/backend`；CBM cwd为WT根。完整argv、开始/结束到秒、exit及log文件名在 [commands.jsonl](../runs/recovery_r11_sbom_inventory_20261016/commands.jsonl)。实际XML逐例计数在 [junit_summary.json](../runs/recovery_r11_sbom_inventory_20261016/junit_summary.json)。最终独立用例合计411，不把中间重复复跑叠加。

| 检查 | 实际核心命令/材料 | 最终结果 |
|---|---|---|
| pure相关unit/contract/security | `python -m pytest`，commands内pure_final完整18文件，`--no-cov -q --junitxml=.../pure_final.xml` | exit0；337passed，0fail/error/skip；unit213/contract30/security94；pytest66.795s |
| 新SBOM真实PG/HTTP | `python .../run_pg.py sbom` → `pytest tests/integration/test_r11_sbom_inventory_postgres.py --no-cov -q --junitxml=...` | 最终6:20:20–6:20:34，exit0；28passed，0fail/error/skip；pytest10.38s；先23、26通过不重复计数 |
| 旧JSON/CSV真实PG | `python .../run_pg.py legacy` → `pytest tests/integration/test_t24_asset_inventory.py --no-cov -q --junitxml=...` | 6:17:45–6:17:52，exit0；46passed，0fail/error/skip；pytest5.39s |
| 全src类型 | `python -m mypy src/ai_intel` | exit0；125source files无问题 |
| 本改动代码/测试 | `python -m ruff check ...`；`ruff format --check --no-cache ...` | final2各exit0；13文件格式一致 |
| 运行材料 | `ruff check/format --config pyproject.toml ...` | 原材料UP022/长行首红保留，修后exit0；最终封存脚本另收据 |
| diff/来源 | `git diff --check`、source/Git-LF/hash脚本、最终CBM | diff exit0，18source/合同文件filtered Git blob对应冻结code |

实际PG为PostgreSQL16.14，loopback127.0.0.1:25432，只从授权WSL connection.json捕获到内存，无stdout/argv/报告DSN口令。三套SBOM独占测试库普通前向0019；最终库 `test_dianzi_r11_sbom_inventory_20261016_062018`。旧fixture只接受0016/0018，独立legacy库 `test_dianzi_r11_inventory_20261016_061743` 普通前向0018，未改变旧fixture。所有库仅测试创建独立sidecar表，标 `test_table_create_not_production_0022`，没有drop/downgrade、删除测试库或用户数据。

CDX/SPDX10000均经过真实认证POST asset-imports、真实PG保存exactraw、GET10000个component与typed source，最后位置/版本无截断；这些输入是explicit synthetic fixtures，记integration，不计真实资产live/性能SLA。

Windows独立venv实际 `uv sync --frozen --offline --no-progress` exit0，Python3.12.13，本地缓存安装83包；首次硬链接回退复制warning保留会话事实（该初始工具输出没有另存文件，不补造日志）。已批准packageurl-python0.17.6在原parser用于成熟PURL解析/strict validation，本切片通过实际dispatcher继续调用；不自造PURL库，不新增依赖。未安装新模型或触发模型/FOFA/付费调用，产品外部费用调用0。

## 定位、红日志与未运行

写业务之前独立CBM source/assets索引与schema/architecture/trace，原JSON保留；source排除独立assets project，需结合两图及源码rg。初source1509nodes/7879edges，assets232/1018；最终source1509/7879、assets253/1132，parse_partial/unusable均0。最终trace显示parse_manifest caller含新dispatcher及原SBOM，InventoryService经dispatcher；图不完整的嵌套路由边用callers_initial/final.txt直接源码核对。索引不是合同和源码的替代。

初把CBM可执行文件当目录、个别读取使用错误backend相对前缀以及PowerShell Byte编码无效，均为工具探索错误，之后用准确路径修正；未计业务失败或补造未保存的文件日志。新unit/security首轮共24例为21passed/3failed：新夹具把已映射/version误列为unmapped，按实际受限profile仅修本新断言并保留首红。首Ruff导入排序/长行、contract长bytes行、材料UP022/长行与seal脚本无占位f-string F541均原日志保留；formatter/有限修正后真实复测绿。Starlette/httpx及旧per-request-cookie弃用warning保留，不以改依赖关闭。

只读核对前端冻结 `1acf4911731f654e11b6173b24db21214d753c02` 的asset-contracts.ts，磁盘/冻结Git blob同为 `f0d3ef11adad3adb0e6f75c60d3725494a364ee4`：source_kind是string，旧strict DTO字段与10000上限兼容；上传类型仅JSON/CSV。此为源码合同检查，没有运行该前端。frontend、browser_e2e、产品live、manual均not_run；不能用另一作者JSON/CSV浏览器证据签SBOM，不能将公开schema可达或synthetic HTTP/PG算live。

生产0022迁移/API app由主控另验，本轮没有执行。原05 imports202异步与当前201同步、analyst WRITE权限差异仍保持既有CR范围；真实资产所有权/清单范围完整性人工核验、产品真值、规则/研判/OpenVEX、性能/持续运行/正式金标均未完成。原CSV方言探索及CPU等其他历史失败不由本切片复现或关闭。

## T24原验收与评分证据

| 原案例 | 本轮证据/限制 |
|---|---|
| C01 合法JSON/CSV一致 | 旧46PG保持投影hash/current复用；新CDX/SPDX真实私有HTTP/PG路径，不能签全部产品资产真值 |
| C02 重复幂等 | raw精确key冲突、语义current复用、并发仅一次outbox、旧请求重放不恢复current |
| C03 版本历史 | 原版本回归与graph-only A→B→A新编号/历史/current/publication |
| C04 不完整不排除 | unknown/空declared_scope仍保留；complete原声明独立sidecar，checksum/graph不冒安装或否定证据 |
| C05 超界非法 | 合法1MiB内10000多字段成功；既有10001/byte/depth/raw-node与新duplicate/nonfinite/NUL/surrogate/共享预算门仍拒绝 |
| C06 tenant/路径 | 原46及新PG认证/CSRF/Origin/ACL/FK/非法路径/失效scope拒绝，原文和opaque不透传 |

F2/F3：仅可追溯库存候选、私有历史与完整SBOM原声明变化。P2：功能边界用例，不是准确率、召回率或错误排除率。E1/D1：真实质量/PG日志与来源冻结；不代表整个系统或优秀评分。

下一项建议：新的非作者reviewer从冻结code/材料复跑337+28+46及自有边界；主控0022生产前向迁移和API app装配后新复核；另授前端explicitCDX/SPDX与sidecar展示切片，再跑真实浏览器和人工范围核验。完整R11/T24/T28保持原验收要求。

未检查：SBOM前端/browser_e2e/live/manual、生产0022/正式API app、真实资产真值与完整R11。风险：未装sidecar表的新SBOM写/读将明确503，启用新格式前须主控迁移；回滚需关闭新格式写并保留历史，不能退表或用旧投影判等吞掉SBOM变化。

最终报告写入时间：2026-10-16T06:25:26+08:00；首次正文创建未单独分秒计时，本记录仅是实际最终装订写入。
