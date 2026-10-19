"""Write the bounded non-author Must 1 recheck from recorded commands."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUN=Path(__file__).resolve().parent
ZONE=timezone(timedelta(hours=8))
started=datetime.now(ZONE).isoformat(timespec="seconds")
report=ROOT/"reports/reviews/recovery/G-E-R17-sbom-workbench-review-1-recheck.md"
counts={"unit_all":"557 passed / 0 failed / 0 pending / 0 todo = 原518 + 新39", "edge_acceptance":"66 passed / 0 unexpected / 0 skipped / 0 flaky = 原18 + 独审38 + 新10", "original_diagnostic":"原2诊断均在bug-presence前置失败；0 passed / 2 failed；不称业务修复失败或原脚本green", "profile_frontend":"原3输入及36手写profile样例满足独立断言；另列，不加进557", "profile_backend":"34/36纯profile相等；2实际CDX文件adapter入口invalid_string拒绝；无HTTP/PG", "material_audit":"非测试：审查helper误将材料tree当源码tree，原红保存", "material_audit_fixed":"非测试：136+2 controls/3source/57旧tests/保护路径均通过", "prepare":"非测试：原120作者+272独审材料392成员及旧输入/断言保护", "finish_audit":"非测试：原392再核、tracked diff0、自己的tsbuildinfo恢复、68文本文件秘密模式检查0命中", "resource_cleanup":"非测试：port26573 listener0 / review node0 / kill0"}
rows=[]
receipts=[]
for path in RUN.glob("*.command.json"):
    value=json.loads(path.read_text(encoding="utf-8"));receipts.append((value['started_at'],path.stem.removesuffix('.command'),value))
for _,name,value in sorted(receipts):
    command=' '.join(value['command']).replace('|','\\|')
    rows.append(f"| `{name}` | `{command}` | `{value['cwd']}` | {value['started_at']} → {value['finished_at']} | {value['exit_code']} | {counts.get(name,'非测试命令，原日志保留')} |")
body=f'''# G-E / R17 · SBOM 工作台 Must 1 非作者定向复核

What this change does: fix1 在原始 PURL 上分离 npm scope 和版本，再分别解码并拒绝版本里的斜杠、@ 与不安全字符。快照组件和 sidecar 引用继续复用同一个展示防线，不生成新的资产或版本事实。

**结论：原 Must 1 已闭合，有限 Ship，仅覆盖这次 SBOM 前端切片。** 未发现新的 Must/Should。作者保持 awaiting_review；root依据本报告登记切片，不由本 reviewer 改 accepted/进度。整R17/T42/G-E、生产默认后端/真实PG0022/browser live、真实授权SBOM、研判导出、人工验收均不签通过。

- 评审人：原非作者 `/root/r17_sbom_workbench_first_independent_review`；本轮未参与实现、未spawn。
- 独立分支 / 目录：`codex/r17-sbom-review1-fix1` / `D:/wt/r17-sbom-review1-fix1`。
- 原基线 / 原源码：`7a653880af12e4160ca8edf26fccbaf5d1e6f0f0` / `406187742a72655bc5f8825f42bc0f1a440af218`。
- 新业务源码：`18d05f1c5842ed7a57f3be9f0351ede4af0b018a`；源码root tree `14689dea97cf0ce897b68680b4c52c882bd22776`。
- 冻结材料 / 审查HEAD：`5587deb124f06b9aa14fb7feb22cdc9493ae4883`；材料root tree `b45c27130647813d239e9d3d11d3efbf2768ff07`。
- 作者报告 `R17-sbom-workbench-fix1.md` Git SHA-256：`6875f503aee43c40a4df9c00924f92e8f34a30add47dcf805fea47d6002e55ac`；作者raw manifest：`eac16b2332e1a1fb6e11d45999f3ccb6c1836a11d1dbe986c592c11ac5dd16f9`。
- 报告写作开始：{started}；结束见文末。初始化建worktree/读文件的完整开始时刻未单独结构化保存，最早自有receipt为2026-10-16T08:51:51+08:00，不补造更早时间。

## 原 Must 1 的触发、修复与实际复验

初审发现 `asset-contracts.ts:74–76` 按解码后的最后斜杠决定是否有版本，使编码私有路径版本变成“无版本”，且允许编码@。原3精确输入保持不变：

1. `pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env`
2. `pkg:pypi/synthetic@review-secret%40private`
3. `pkg:generic/synthetic@%252Fhome%252Freview-private`

fix1实际改动为 `frontend/src/features/assets/asset-contracts.ts:67–88`：raw npm scope先分离，raw path `lastIndexOf('@')` 固定版本，package path/raw version分别解码，残留percent/控制/URI字符拒绝，decoded version `/@`拒绝。`parseSnapshot:101` 与 `sbom-contracts.ts:73` 两个真实调用方未改，仍抛 `AssetResponseScopeMismatch` 并使用原M01同步撤销。旧JSON/CSV不增加这个SBOM fence；scope、hash、shape、安全URI、redaction alias及来源版本unknown保持既有语义。

独立Node probe中，原3输入的helper均false，snapshot与reference均抛精确ScopeMismatch。新独立Edge正确验收使用原3输入 × snapshot/reference = 6条：全部看见撤销消息，私有资产/快照/历史/上传File DOM均清空，危险原值0处，浏览器持久存储0；snapshot路径在sidecar GET之前已拒绝。另4条合法npm scope（raw/encoded scope，有/无版本）每条在组件与关系两位置可读，没有误撤销，均取得固定SBOM声明。六拒绝/四合法的PNG与JSON实际保留并核对应结果，不以build替代浏览器。

原两条诊断先断言旧bug泄漏可见，再截图，再断言应撤销。保留原完整script字节 SHA `eb72ec82f8c962002c0695634a1053344d3c04d8191cbad9d289663990801155`；本轮resource adapter只将26173改为26573，输入/断言不改。原两条按原断言复跑 **0 passed / 2 failed**、exit1，失败在“PURL应可见”前置；新error-context与失败PNG实际显示已清除私有工作区，原泄漏值不在DOM。这是修好后bug-presence诊断的预期结果，**不是把原脚本称green，也没有修改原诊断后伪装通过**。正确验收6条与原诊断2条分开保存、分开统计。

初审原snapshot/ref泄漏PNG、附件JSON、两份error-context及needs_changes报告没有覆盖；它们随原272成员前后hash保护。作者fix1中另一次旧源码red复现与其两精确error-context也通过136材料Git byte检查，现正确验收不替代原红证据。

## 固定后端与外部文件边界

本轮从Git `5be873ec38a41955b5a58e9762df4b866a7a9d63` 提取backend/src到自己的run/probe，从未以作者活动目录作通过来源。实际调用 `_safe_purl_reference` 对36手写输入校准：34/36直接与前端相等。原始tab/newline两个纯helper差异仍保留：Python URLsplit剥除它们后返回true，而前端直接拒绝。

这两条另外实际作为UTF-8 JSON上传文件bytes（CycloneDX 1.6），进入该冻结后端的导出 `parse_inventory_input` dispatcher，并使用明确synthetic认证scope。均抛 `SbomValidationError`、code=`invalid_string`，未产生规范快照；`backend_profile_probe.json`保存两个实际原文件hash和异常类型/代码。前端现字符串边界与PURL helper也拒绝它们。因此这两种输入在实际文件适配入口被拒绝，**不是只相信作者说它们会被拒绝，也不是声称36个纯profile全等**。此探针没有运行HTTP router、连接PG或读取真实资产；SPDX这两个控制码分支未另做独立adapter调用，生产外部HTTP验收继续未覆盖。

原8个跨语言serializer合成DTO测试随旧518回归通过；此次额外后端探针只校准profile/实际文件适配边界，不把它提升为PG持久化、生产默认app或SBOM live证明。正确safe PURL只是安全展示声明，不等于安装范围/依赖或版本风险已核验。

## 调用链、材料与保护

本轮再次按AGENTS/00/R11/R17/T24/T42/03/04/05与冻结task_state核对，沿用已读最新版Ponytail review5.2。工业terminal UI与用户ui-design仍只作设计数据；CSS/App/动效未改。独立CBM frontend/src full为733 nodes / 2957 edges，not_indexed/skipped/parse_partial/unusable均0。depth3 `isSafeSbomPurl`有14入向调用者；另保留depth4的18入向输出，深度不同不混作分母。

CBM App depth2、SbomDetail both depth5与排除test文件的`source_trace.log`确认真实链：`index.html → main.createRoot → App → Workbench → AssetWorkspace → AuthorizedAssets → AssetDetail → SnapshotView → SbomDetail → getAssetSnapshotSbom → parseSnapshotSbom → reference → safeReference → isSafeSbomPurl`；snapshot直接由`getAsset/getAssetSnapshot/importAsset → parseSnapshot → isSafeSbomPurl`约束。exports/默认App/Vite代理路径均从生产源码核对，不只有test calls。父节点scope撤销、旧结果不能恢复和普通503局部保留仍通过原一般38与原18。

新材料136成员的Git blob hash/长度全部匹配manifest，加manifest/sha共138。三个source files在18d与5587逐字相同；相对7a只有helper与两个新test文件，**57个旧test/spec Git内容不变**。backend/public contracts/根锁/root attrs/progress受保护路径diff为空。作者报告checkout自动转CRLF，唯一该报告的检出字节与Git raw有差异；权威hash按冻结Git blob，没声称checkout report raw也匹配。

首次material audit红是本reviewer把给定b45误当18d source tree；实际b45精确对应5587材料tree，source tree为14689...。校准后原红保留，源码三文件/材料hash均相同，没有把真实差异忽略或改目标SHA。

原作者118成员+2 controls=120从原7a Git与新5587 Git对比；原review272成员从我自己的封存WT逐个raw核对；共392前后漂移0，另两review manifest controls也前后保护。原error-context空白原byte未trim。fix1冻结generated_format_receipt与原两exact attrs例外已读：两个error-context hash与Git blob相同，generated_fixture仅EOF变更receipt为非EOF内容相同，不涉及原输入/断言。**本review没有改任何attrs**，没有借此放宽源检查或修改材料。

## 独立实际验证

unit为 **557 passed / 0 failed / 0 pending / 0 todo** = 原518 + 新39；39是36profile参数例及原3Must精确类型断言，不说成39个新增独立输入。额外Node/后端probe不加进557。原518测试均未改；原8合成serializer仍包含其中。

正确验收Edge dist为 **66 passed / 0 unexpected / 0 skipped / 0 flaky** = 原18（旧12+原SBOM新6）+ 我原38一般检查 + 本轮新10（六撤销+四npm合法）。原两bug-presence诊断0/2另列，不参与66正确验收分母。port26573，自己npm ci安装299包、自己dist真实浏览器；没有使用作者活动dist或kill他人node。typecheck/lint/build均exit0。

原18和一般38保持fixture标签可见，覆盖四格式raw File、10k只渲染20行与分页、unknown/empty/history、深编码URL/private IP/userinfo/标准化、bad locator/hash/type/shape/alias、晚到parent/fixed/SBOM 401/403/confirmed wrong-scope全workspace撤销、503可重试保留授权页面、历史不被late current覆盖、390px键盘与局部表格滚动、动态拓扑正常动画/reduced-motion关闭、安全文档no-referrer/no自动外域fetch。工业研究台的暗底/信息层次/动态背景得到实际截图和行为回归，没有仅以形式或行数验收。

秘密模式检查实际扫描3个source文件及本review文本产物，首末审查scan记录68文件、5类key patterns、0命中；后续最终封版另将本报告及封版脚本纳入扫描并记录scope。二进制、提取的不可变backend源码及scanner定义不在该模式检查范围。实际凭据取得0、付费调用0、第三方资产扫描0；不声称生产allscan、secret扫描没有读取环境变量或生产秘密。

### 命令、退出码与时间

全部人类时间为真实+08:00，完整argv/cwd/start/end/exit在同名command.json；原输出字节在同名log。Playwright JSON startTime保持原UTC。未执行的业务层测试见下一节。

| receipt | 实际命令 | cwd | start → end | exit | 实际数量 / 限定 |
|---|---|---|---|---|---|
{chr(10).join(rows)}

## 状态、未覆盖与交接

| 项 | 本轮结论 |
|---|---|
| Must1 | closed：原三输入、两调用方及6条正确DOM撤销独立通过；原旧诊断按设计前置失败，保留历史 |
| unit / contract | passed：557；36校准是34profile直接相等+2实际adapter拒绝；不重复分母 |
| frontend / synthetic security / fixture e2e | passed：type/lint/build0、66；权限/旧响应/错误/页面边界均在上述范围内 |
| backend integration / PG0022 / default API | not_run，未签；未改Python故不宣称Ruff/mypy或后端全回归已跑 |
| live | blocked / 未取得：真实授权SBOM及默认生产API/browser live；fixture不是live |
| manual / 录像 | not_run；原生hidden页面、人工全场景和连续演示未验 |
| R17/T42/G-E | 保持partial/未过阶段门；研判/四态/证据导出、外部观察、原T42六项合并验收不提升 |

本轮改动仅新report与`reports/runs/recovery_r17_sbom_workbench_review1_fix1_20261016/`内review/probe/log/PNG。自己的tracked tsbuildinfo恢复至HEAD原byte，tracked diff0；main用户文件、业务、原测试、公共DTO、后端、锁、认证、attrs与progress均未修改，未提交/push/publish/spawn。port26573监听0 / 本review preview node0 / kill0。

F2/F3只登记获授权清单输入与固定声明展示的有限切片；不把purl安全子集当版本研判、当前风险或安装真值。D2/E1/X1有真实桌面/窄屏、键盘、同步撤销和独立证据闭环；真实业务/完整评分和演示尚未验。

下一步由root根据本非作者定向复核登记并集成该frontend切片；继续核生产资产/SBOM默认路由、PG0022、真实授权browser/live与研判导出之前，保留对应阻塞和阶段门。旧needs_changes报告仍是旧版本事实，不覆盖历史。

Verdict: Ship. 仅签冻结18d05/5587的SBOM前端切片及本次Must1修复。

Not checked: 生产默认API/PG0022/browser live、实际授权SBOM、研判/导出、完整R17/T42/G-E、人工与连续录像。
'''
ended=datetime.now(ZONE).isoformat(timespec="seconds")
report.write_text(body+f"\n报告写作结束 / 证据截止：{ended}\n",encoding="utf-8",newline="\n")
print(json.dumps({"report":str(report),"started_at":started,"finished_at":ended,"verdict":"limited_ship","must1":"closed"},ensure_ascii=False))
