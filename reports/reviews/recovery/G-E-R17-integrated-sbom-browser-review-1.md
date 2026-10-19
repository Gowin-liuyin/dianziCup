# G-E / R17 · 默认真实后端 SBOM 浏览器切片独立首审

What this change does: 本次改动为固定 SBOM 快照增加六类声明的页内导航，并按该快照的 component_id 显示已保存的组件名称。它继续通过默认 FastAPI、真实 Cookie 认证与 PostgreSQL 读取声明，不计算新的安全或影响结论。

**结论：产品源码限定 Ship。本轮未发现未关闭的产品 Must fix / Should fix。** 候选 `f1f2` 的干净检出缺原八个 serializer 案例所需资源，直接 unit 亲复失败；挂载精确原件后的557与实际默认PG/API/Edge九例通过。主控必须集成原资源提交 `6be1d1b2f2101bea58b488531dbfb1f83fcdc0ce`，最终主控集成 SHA 的 freshGit 复验另列，不能把本轮资源适配说成 `f1f2` 自包含。整 R17/T40–T44/G-E 仍 partial，作者仍 awaiting_review，本审不修改 accepted 或 progress。

- 非作者评审：`/root/r17_actual_backend_sbom_browser_first_independent_review`，未参与实现、未 spawn。
- 自建分支 / 工作树：`codex/r17-real-sbom-browser-review1` / `D:/wt/r17-real-sbom-browser-review1`。
- 固定主控基线：`17ab90e0a6b100530a3078dd525f9086813c9728`。
- 作者源码：`4a17fa3fb7357a8c2b9d647f62c875958a24a27d`，source tree `c5d3f2642f64ca00952aa70491e2ad2e8a3b846c`。
- 完整冻结材料 / 审查 HEAD：`f1f2bc49ccd33be7e0b150482b253399a4ad7c64`。
- 原 SBOM 前端材料：`5587deb124f06b9aa14fb7feb22cdc9493ae4883`。
- 自有证据：`reports/runs/recovery_r17_integrated_sbom_browser_review1_20261016/`，下称 own run。

## 范围、规范与实际调用链

读取 AGENTS、00 execution map、恢复 R17/R11、T40–T44、03/04、R11资产/sidecar/默认reader与privacy补充合同、作者新报告及原 R17 PURL Must1、R11 privacy独审报告。采用插件 Ponytail review 5.2；本用户要求中文报告优先于 skill 的 English 建议。用户黑客风、动态背景和减少动画偏好依现有设计合同审查，未套入营销布局或新增依赖。只审这次 SBOM 真工作台切片，不签来源/模型/FOFA/VEX/Agent 整平台。

源码相对17ab只有五个路径：`frontend/src/features/assets/sbom-detail.tsx`、`assets.css`、`frontend/e2e/r17_integrated_sbom_api.spec.ts`、`helpers/r17-sbom-inputs.ts`、`helpers/r17_sbom_control.py`。前两者为产品改动，后三者为直接验证。本人逐一比较17ab、5587、4a17和f1f2，原 **58 个** `.test/.spec` 文件的集合与 Git blob 全相同；五源码文件在4a17/f1f2也相同。全部58保护，未沿用旧材料对不同基线57的计数。原测试、金标、分母、权限、后端、迁移、合同、依赖锁、progress均未修改。

独立 CBM 0.11.0：frontend/src full **735 nodes / 2964 edges**；backend/src fast **1922 / 10614**，明确排除assets，另补assets full **263 / 1184**。三者 not_indexed/skipped/parse_partial/unusable均0。实际执行 schema、architecture 和带project前缀资格名的5个depth4 trace，原CLI JSON与argv/时间收据保存在own run。最初全工作树索引在own材料同时写入时返回 `aborted_previous_preserved`；该工具输出仅有会话记录、无磁盘原stdout/完整起止，不补造，通过结论只用后面的冻结source索引。

图与随后源码rg共同核对：`main → App → Workbench → AssetWorkspace → AuthorizedAssets → AssetDetail → SnapshotView → SbomDetail → getAssetSnapshotSbom → fetchJson → parseSnapshotSbom`。frontend trace显示4入向/36出向节点。backend default factory创建PG目录与PgAuthenticationStateStore，并把同一个inventory router注册到 `/v1` 和 `/api/v1`；资产router在同Session重新锁当前认证scope与READ_ASSET/WRITE_ASSET。库存读取按tenant/asset/snapshot联合条件查询冻结payload及raw/projection/sidecar/combined绑定，再执行安全view。窄assets图未呈现嵌套HTTP handler caller，不能据缺边宣称无调用；实际路由源码与真实请求都已确认。

生产forward链实际到 `public / 0022_sbom_sidecars`，未create_all。原文唯一存于 `asset_snapshots.raw_input`；0018快照与0022 sidecar的不可变trigger均独立实测。当前指针更新与追加历史在原业务事务内。历史显示固定快照，当前与历史分别读取的新版本冲突显示REVALIDATE，不被前端重算成安全。

## 必须保留的资源缺口

1. **候选干净检出缺原 serializer 资源**（`frontend/tests/r17_sbom_backend_contract.test.ts:7`）
   - 职责：原八条跨语言serializer测试读取固定后端DTO样本。
   - 实际问题：fresh f1f2直接跑unit得到549通过、0失败断言、1 suite ENOENT；八条根本未加载，不能写557通过。
   - 最小修法：恢复原路径 `reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json` 的原blob `82c40263274fb65517037ab5e3f2d3982f151d67`，及其精确run-local attrs，使检出原件仍为raw SHA256 `92f5a0cac56ccd97c63af16bd14418cbc1c42cf4803c3ab6627f419235a6e331`，27787 bytes；不改测试或重新生成样本。
   - 若遗漏：下一次fresh检出仍不能执行原完整unit。本审经主控明确授权仅作临时exactresourceadapter，原字节备份与适配收据保留；主控随后已提交6be1d1b，本人亲核该commit的fixture blob精确82c402。f1f2原缺口未被追写成不存在，最终集成cleanGit命令仍须独立复验。

这属于交付资源缺口；产品源代码本轮没有Must/Should发现。修法没有放宽serializer期待的 `backend_material_sha=5be873…`，旧八条仍作为合成合同，不计真实端到端或live。

## 真实默认后端复验

重PG测试先向root申请，获唯一serial slot后执行，完成立即释放。自有新库 `test_dianzi_r17_real_review1_20261016`，run_id `r17_real_review1_20261016`，own网页26873、默认API28873。DPAPI仅指定pwsh7子进程在内存读取获准本机test参考，核loopback25432、test账号与原数据库后派生自有库；DSN/随机口令不进argv/日志/截图。未重启共享服务、复用作者库、降级旧库或终止他人会话。

原六个spec的副本只替换三个import/control资源路径，输入、断言未变。API/runner只适配run_id、端口和own config；为新增负例随机建立11个各自租户的合成账号，绝不输出口令。普通 `create_application(settings=...)`，无注入auth_service、monkeypatch engine/业务方法或route.fulfill。实际已安装Edge访问本WT dist并同源代理；显式 `app_env=test / data_mode=fixture` 与界面“合成 Fixture · 非真实资产”标签保留。因此这是**真实本地默认API/PG/Edge合成数据端到端**，不是外部真实SBOM产品live。

| 独立实际案例 | 输入与可观察结果 |
|---|---|
| 原API01 | 真登录、200空目录、原CycloneDX UTF-8 File POST201、PGraw SHA与上传一致、public0022；名称/原purl/字段位置/typed sidecar正确；Enter导航聚焦固定section；私有URI隐藏；真实3秒表锁下loading可见 |
| 原API02 | 第二租户读第一fixed sidecar404，body无tenant/components/私有标题；SPDX DESCRIBES/purl可见；公开href保持惰性，file URI为null且危险原值/链接均不在DOM |
| 原API03 | UI追加版本1/2/缺版本三快照；冲突purl/version原输入422；#1固定hash和空关系保持；reload恢复#3；实际第四快照仅刷新历史产生REVALIDATE，刷新资产恢复#4；旧#2仍有原关系 |
| 原API04 | own sidecar表临时改名导致actual GET503；组件继续可读、旧sidecar/hash不显示；finally恢复表后重试200和原hash恢复，无伪造安全结果 |
| 原API05 | 实际PG role降viewer后的第一个资产403清空私有列表/历史/File DOM；实际PG会话撤销后401清空私有workspace；local/session storage0 |
| 原API06 | 25组件真PG持久化；390px整体不横溢出，Enter组件页20→5；声明区focus正确；reduced-motion animationName=none，正常motion两帧且computed transform确实变化 |
| 自有N01 | 在390px逐一Enter六类导航，包括0项区，六target全部focus且无整体横溢出；独立SBOM组件来源分页20→5、最后synthetic-extra-22名称可见，再回20 |
| 自有N02 | 中文名称和末尾空白的原UTF-8 bytes精确保留；仅依赖变化A→B→A产生3唯一快照、前驱链正确；原HTTP请求重放返回#1但current仍#3，原fixed sidecarJSON完全相等；快照与sidecar的UPDATE/DELETE共4次全部SQLSTATE23514，且每次finally rollback；历史原hash/中文名称/空关系可读 |
| 自有N03 | 新两租户分别登录；foreign资产详情、history、fixed snapshot、fixed sidecar四入口各404，响应无tenant/snapshot/components/私有标题；foreign深链DOM无原title/rawhash/history |

最终 **9 distinct案例，原6/6 + 自有3/3，0unexpected/skip/flaky**。没有把重复层、4次trigger或四个foreign入口额外加成新browser分母。32 PNG（16 full +16 viewport）、9份只记录path/method/status/time的HTTP flow、真实PG核验与原合成上传字节保留；登录页不截图，无video/trace/自动失败截图。本人实际查看desktop全文、390viewport/全文、stale、503和403图片。截图支持本切片布局与状态，不等于人的最终manual验收或连续操作录像。

实际SessionId=1，与runner桌面会话匹配；boot验证PID或launcher parent、nonce、默认factory源码路径与started。两轮API stdin正常stop、lifespan完成、exit0；NullPool bootstrap/control/audit engines均dispose。两轮ownPG其他连接0、26873/28873监听0、原sidecar表存在/临时名null。没有用“外部不可达”解释软件修复。

## 实际命令、起止与失败

人类时间+08:00。解释器 `D:/dianzi/backend/.venv/Scripts/python.exe`，Node24现有精确锁依赖通过本WT ignored node_modules junction复用；未在作者dist执行。下面完整argv/cwd/起止/exit分别在同label `_command.json`，原stdout/stderr在`.log`。初始读文件/建WT/prepare/audit的部分命令没有单独结构化时间，只有会话工具退出记录，不补造。

| own receipt / 实际命令 | cwd | 起止 | exit / 数量 |
|---|---|---|---|
| unit_fresh：node node_modules/vitest/vitest.mjs run --reporter=json --outputFile=own/unit_fresh_result.json | frontend | 11:09:57.503–11:10:30.469 | 1；549pass、0fail断言、1ENOENT suite、0pending |
| unit_adapter：同命令写unit_adapter_result.json | frontend | 11:12:18.532–11:13:05.387 | 0；557/557、0fail/pending/todo/suite error |
| lint：node node_modules/eslint/bin/eslint.js . | frontend | 11:12:18.582–11:12:26.262 | 0；非业务测试 |
| typecheck：node node_modules/typescript/bin/tsc --noEmit | frontend | 11:12:18.632–11:12:27.285 | 0；非业务测试 |
| build：npm.cmd run build | frontend | 11:13:30.266–11:13:35.064 | 0；本WT dist |
| original_six_run1：python own/browser_runner.py original_six_run1 → node @playwright/test CLI test --config=own/playwright.actual.cjs | WT根→frontend | 11:16:42.792–11:17:09.365 | 0；6/6真实defaultAPI/PG/Edge |
| independent_probes_run1：R17_REVIEW_SPEC=independent_probes.spec.ts，python own/browser_runner.py independent_probes_run1 →同CLI | WT根→frontend | 11:17:25.997–11:17:40.241 | 0；3/3真实负例 |
| 三个cbm index：WSL CLI index_repository，full/fast/full、persistence=false | WT根 | 11:14:15.612–11:14:23.067 | 各0，范围见前文 |
| 五qualification trace：SbomDetail/create_application/get_snapshot_sbom/lock_authenticated_scope/import_manifest | WT根 | 11:17:34.734–11:20:14.422，各自receipt | 各0，CLI isError false |
| 三schema/三architecture | WT根 | 11:16:01.694–11:21:35.161，各自receipt | 各0，非业务测试 |

本review只有fresh资源ENOENT这一次验证红，未改断言、skip或测试分母；三个自有负例首执行通过。工具层初次全repo CBM abort另列。原作者误用npm exec、Windows launcher/Session判断、File postDataBuffer不可用、422冲突输入、locator/撤销等待、serializer缺资源与材料工具红均在289原件内保留；原作者最终6green不作为本审自己的通过来源。

## 原件、设计、安全与剩余验收

作者 `evidence_exact_raw.tar.gz` SHA256 `ff1fb42713245309de38bc641a98084cb6c7121cbf2885d20501c7f8a4465bbf`，本审逐个校验289成员raw size/hash全一致。Windows本WT的159个作者checkout文本raw与manifest不同，准确记录于material audit；权威原raw仍在完整archive，未覆盖或修剪任何原红例。Git源码身份与原raw材料身份分开，不能把CRLF checkout称为原raw。own run `.gitattributes`只限定own输出`-text`，用于保存收据/日志/原件字节，无共享attrs、检查忽略或业务变动。

实际黑客风为近黑色表面、青绿主强调、琥珀未知标签、等宽摘要/定位，窄屏局部表格滚动。背景低亮SVG拓扑在外围/留白可见，正文面板不透明；实际正常motion和reduced-motion都测到预期。不凭好看推业务能力，源组件/完整性/checksum都保持“声明/未核验”。六导航焦点和分页并未改App hash或篡改current，DTO/parser拒绝边界仍由原557回归与真实权限拒绝覆盖。

两轮runner在随机口令仍在内存时对74/107个文本文件进行精确秘密扫描，命中0；flow不保存headers/cookies/密码。主用户 `D:/dianzi/frontend/tsconfig.tsbuildinfo` 只读，全部receipt SHA仍 `3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d`；自己的build产物已恢复HEAD。未push、公开发布、下载模型、调用收费API、外部URL抓取、第三方资产扫描或PoC运行。

有限证据：F2/F3为原文hash、typed声明、固定历史/来源定位/unknown；D2为桌面390/键盘/动态背景及真实错误状态；E1/X1为默认认证/PG0022/跨租户/撤权/恢复。T42-C02仅缺版本/来源未知，观察时间缺失仍拒绝；C04只证明追加历史与current，不证明研判重算任务；C05只证明current-pointer revalidate，不证明assessment freshness；C06未就绪限制可见，真实OpenVEX未验。C01不同版本真实影响判定、C03真实FOFA路径/修复判断、T41来源/原文修订、T43问答/Agent/订阅与T44监控计分均未验收。

Not checked: 最终主控集成SHA的freshGit完整557，外部真实授权SBOM资产/模型/FOFA、VEX/Agent、正式金标评分/吞吐性能/持续运行、人的manual与连续录像。fixture六例只属原合同，不计本轮live；本轮实际九例使用合成数据的真实本机默认链路，不升级外部live。

Verdict: **Ship，仅本SBOM工作台产品切片；集成必须携6be原资源，并对最终主控SHA补freshGit复验。** 后续按R17余下已冻结业务接口推进研判、导出、问答Agent与推荐，保留全部原验收/阶段门。
