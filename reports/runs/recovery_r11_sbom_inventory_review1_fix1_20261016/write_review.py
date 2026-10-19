"""由实际收据生成复核报告；旧红灯单列，重复执行不扩充分母。"""

import gzip
import hashlib
import json
from pathlib import Path

from review_runner_final import ROOT, RUN, now

REPORT = ROOT / "reports/reviews/recovery/G-D-R11-sbom-inventory-review-1-recheck.md"


def main():
    receipts = [json.loads(line) for line in (RUN / "commands.jsonl").read_text().splitlines()]
    index = ["# 本复核实际命令索引", "", "所有时间为Asia/Shanghai；argv精确内容见commands.jsonl。backend表示独立WT/backend，WT表示独立WT根。", "", "|编号|命令标识|cwd|上海起止|exit|用例/检查数|raw路径|", "|---:|---|---|---|---:|---|---|"]
    audit = json.loads((RUN / "final_source_audit.json").read_bytes())
    for number, entry in enumerate(receipts, 1):
        result = audit["independent_junit"].get(entry["name"])
        counts = f"{result['tests']}例/{result['passed']}过/{result['failure']}败/{result['error']}错/{result['skipped']}skip" if result else "非功能用例命令"
        location = "backend" if Path(entry["cwd"]).name == "backend" else "WT"
        index.append(f"|{number}|{entry['name']}|{location}|{entry['start']} → {entry['end']}|{entry['exit_code']}|{counts}|{entry['log']}|")
    index += ["", "未进入command()的准备与读取不补造收据：uv_sync_receipt.json有独立真实起止/exit0；prepare_final.py的最终校验start/end见final_material_verification.json，工具exit0、135清单项/214原test blobs。legacyfinal首次数据库标识65字符被PG截短，前置guard异常exit1、0测试执行，完整栈见legacyfinal_runner_error.log，没有磁盘完整起止收据；仅缩短自有mode并用fresh DB复跑。git FF与源码/doc读取为会话工具记录，未虚构原stdout日志。"]
    (RUN / "command_index.md").write_bytes("\n".join(index).encode())
    measurements = json.loads((RUN / "sql_capacity_measurements_final.json").read_bytes())
    report = f"""# R11/T24 SBOM库存与容量 · 独立初审1定向复核

本次改动为SBOM安全展示补上来源URI、引用、编码PURL和未知字段定位边界，保留不可变原文、组件身份、摘要与历史。结论：**有限 Ship**，只覆盖本批库存/容量/独立侧车表服务与本次privacy修复；原发现1及742追加两类Must已由下述新冻结版本独立复跑关闭。本报告不签整阶段、R11/T24/T28、生产迁移、正式app或浏览器/live。实现状态仍由主控登记，未改progress/accepted，没有提交或push。

评审人仍为非作者 `/root/r11_sbom_inventory_first_independent_review`。独立WT `D:/wt/r11-sbom-inventory-review1-fix1`，branch `codex/r11-sbom-inventory-review1-fix1`。旧初审报告与原97项seal保持在 `D:/wt/r11-sbom-inventory-review1`；原结论needs_changes、4个官方合法输入真红与所有首红均保留。本次生成时间：{now()}。

**冻结身份与材料**

被审业务source：`6942c65efd5df013c077275cbb6d8cfec3585080`；material与本WT HEAD：`5be873ec38a41955b5a58e9762df4b866a7a9d63`。历史链c036→742→b4→6942，未在最终材料之后改业务。作者报告raw SHA256 `b077cce059bf79ef1d82d69b2d1c2fdd1907f1c8765deabb24ef25254f4e52c4`；manifest SHA256 `95536bffce7cdbcf530fdb8d6a05a7a80a28f260a1babf895b211de072a3325b`。本人逐一核对135个indexed raw条目，另两个控制文件artifact_manifest/seal_receipt单独记录；report_raw.md.gz解压精确原文同时与material Git LF字节相等。作者控制文件material_commit:null是材料提交前生成时事实，最终5be身份由本审实际HEAD/source blob补证，不用null自行猜提交。

作者source proof也经本人Git核验；c036原214个backend/tests blob全部不变，33条前轮privacy unit、22条PG及typed DTO与b4相同；pure parser、容量manifest parser、50k共享strict JSON、表、原路由/旧DTO、依赖锁与progress仍与c036相同。最终8个变化路径是3业务文件、4直接测试和1批准CR；19个Git LF源blob另gzip保存于final_source_blobs，raw SHA与GitLF SHA分列在final_source_audit.json。root表0532的Git blob仍等于本版表。原97项manifest SHA `0cc00f729e88152ccf4f527f6861f21c19709be303c8e73bd30844414a77f5a7`再次逐字节核验，97项全一致，原review报告没有覆写。

本审使用ponytail-review 5.2.0，并读AGENTS、00、恢复R11及原T24/T28、03/04/05/06、SBOM adapters/sidecar/table/capacity/dispatcher及资产CR、任务报告与本次补充CR。权限和范围按主控已批准的最小展示修复执行，普通name/display/自由文字没有扩成万能secret黑名单。

**发现的关闭及保留红灯**

原c036发现1为同租户READ_ASSET analyst收到受保护SPDX URI或CDX引用，而非跨租户泄漏。本人保留并以完全相同字节重跑原18＋compatibility3＋digest3，24/24通过；另33unit/22PG覆盖源URI→nullable None、typed标记、alias碰撞与schema1历史。危险CDX bom-ref、dependency/composition统一同原值sha256 alias；客户端伪redacted-ref前缀仍再hash，合法公共HTTP声明保持惰性可见。原raw不改，摘要/身份不因安全展示改写。历史先做租户/ACL及冻结身份/adapter/spec/raw/projection/sidecar/combined校验，再投影，不重解析当前parser。

742版本本人实际跑369pure、50PG、46legacy、24原probe全绿；新11 probe 7绿/4红，其中deep5/8编码键与重复locator错值为3个业务真红，最后1红是本审编码PURL fixture同时保留version1造成源冲突422。只移除该自有fixture冲突version后原期望不变，定向1绿。追加旧schema1/新schema2的None缺标记2条均真实红，归入相同精确来源绑定根因。原11首执行gzip、pg_new.log/xml、pg_corrected.log/xml、pg_nullmeta.log/xml都保留；五条业务红按**两类Must**计，不把自有fixture错误算业务，不重复扩大风险数。

最终原13 probe源bytes10471、SHA256 `1b6862cd8b1b35572513ff698788768d826d8bfc885146021c66f510bd87a8d5`完全不改，本人新库13/13通过。最终解码仍最多4轮，标准库strict UTF8并拒绝每轮非法escape和残余percent，深5/8/12/64、不完整percent、非法UTF8/代理码/NUL均转为typed固定定位占位。原字段反JSONPointer转义后的原bytes决定hash，不同编码原键不合并；普通Unicode仍可见。schema2每次重复定位都先核固定reason/精确replacement/value及同定位值一致，合法重复同值保持拓扑与二次投影幂等；错值/额外/重复/冲突metadata固定503。schema1原URI不能无出处变None；schema2 None必须精确标记。上面五真红只用最终6942的相同probe关闭，未把b4静态阅读或作者绿当复验证据。

本审另外9条最终HTTP边界首轮8过/1 fixture红：错误把已有document再加同ref b且留下悬空composition，入口422正确拒绝；原pg_edgesfinal.log/xml与首执行gzip保留，只改该自有fixture构造为3个唯一ref，业务断言不变，fresh DB定向1过、8 deselected。7种非法编码键、四种深度不同原键定位不碰撞/合法Unicode、重复图GET不重进parser均已实际执行。原13/18/24及作者测试未改。没有未关闭Must、Should fix或用风格猜测制造的发现。

**实际独立命令与分母**

所有结构化命令精确argv/cwd/上海秒级start/end/exit/raw路径在本run commands.jsonl；逐条编号和检查数见command_index.md。解释器为本WT backend/.venv/Scripts/python.exe，pure/PG/quality cwd backend，CBM/审查audit cwd WT。无外部schema下载，已有官方CDX1.5–1.7及SPDX2.3冻结schema在独立probe中实际离线validate，不把HTTP TestClient称live。

|最终命令/raw日志XML|上海起止|exit|结果|
|---|---|---:|---|
|pure_final|07:31:18–07:33:05|0|396 passed：unit272/contract30/security94；原337＋新33＋26；0fail/error/skip；104.96s|
|pg_sbomfinal|07:31:49–07:32:11|0|59 passed：原28＋22privacy＋9followup；19.08s|
|pg_legacyfinal|07:31:49–07:31:56|0|原46 passed；4.39s|
|pg_oldfinal|07:31:20–07:34:11|0|原18＋3＋3共24 passed；167.91s含官方离线schema，不当HTTP时延|
|pg_newfinal|07:31:20–07:31:26|0|原13 passed；3.94s|
|pg_edgesfinal|07:32:51–07:32:55|1|新9首执行8pass/1fixture error assertion，1.87s；0skip|
|pg_edgescorrected|07:33:29–07:33:32|0|同case修自有fixture后1pass/8deselected，0.32s；不重复加分母|
|mypy_final/ruff_final/format_final|07:34:09–07:34:11|0各|全部125source无类型问题；最终7改动Python源码/测试Ruff及format通过|
|callers_final_rg、CBM资格名8trace|07:34:11–07:34:35|0各|新冻结tree actual CLI JSON结果解析，0 MCP isError|
|audit_final|07:35:03–07:35:07|0|作者/旧seal/源码blob/实际XML实核|

最终唯一功能用例 **547**，末态均通过：原411＋privacy/followup90＋本审46（24＋13＋9）。新增9的最后case仅作必要定向复验；742与c036重复运行、首fixture红、质量/环境检查均不累加分母。Starlette/httpx、anyio rewrite和原cookie弃用warning完整保留，未关检查或改依赖。早期742 own材料Ruff/format红和纠正记录在commands索引，不冒充业务红；旧probe原bytes及执行版gzip亲核。未知/无资源不改skip，最终功能集合0skip。

**真实PG、容量与连通证据**

资源仅读取批准WSL本机test参考到内存；DPAPI fallback代码按批准范围保存，本轮实际资源来源见各database.json。host loopback25432、user/test_dianzi专用前缀均guard；fresh DB run_id严格r11_sbom_review_fix1_...，legacy另r11_inventory_review_fix1_...；运行编号仅对本审隔离资源生效。SBOM前向0019＋局部独立sidecar Table.create，legacy前向0018，原16/18 fixture断言不变；不把测试表创建当生产0022。首次legacyfinal库名65字符被PG按63截短，current_database guard在pytest前拦截，0例执行；只缩短本审mode为lf并创建fresh库，无降级/删除。所有资源库保留，不复用root已停止服务DB，不drop/downgrade/flush，不触采集器/queue15/API或MinIO。

原24亲跑验证表PK/三列tenant FK、hash/版本/JSONB/NOT NULL、snapshot raw与sidecar不可变触发器；receipt最后失败全事务assets/raw snapshot/sidecar/current/epoch/change/outbox/receipt回滚。原28验证graph-only/opaque-only/checksum-only/composition-only变化都新history/current/outbox；空白对象键序语义复用，raw精确幂等冲突、A→B→A、历史请求重放不恢复旧current、并发只一次发布。combined用于新SBOM判等，旧projection/hash/DTO不改。普通checksum非image_digest，dependency图非runtime path，composition非inventoryconfirmed，未知生态无安全/installed升权。

sidecar和公共snapshot四read入口、POST新响应与replay均有编码credential PURL的只读None实测；内部canonical/raw/组件身份与hash仍原值；JSON/CSV46回归通过。analyst同租户只读200、foreign404、最新角色/ACL撤权403、匿名/撤销401、Origin/CSRF/tenant extra拒绝由原PG及本审probe覆盖。损坏stored shape/digest/metadata都503，不吞empty或fake pending，不泄foreign存在/身份。历史GET在parser换成抛异常后仍200并payload不变，raw未被重新解析。

10000多字段CDX1.5/1.6/1.7/SPDX官方有效输入各完整返回，版本/source与尾部组件不截断；CDX1.5实际HTTP输入精确1MiB。局部strictstdJSON的810163键值预算数学及完整字段/64路径边界通过；共享50k、SBOM200kraw节点、1MiB、depth16/10k/duplicate/NaN/surrogate/NUL/custombad都保留。原两个projection_node_limit用例按root CR批准同input/schema改10000成功，旧DID NOT RAISE与三个首红仍保留作者旧封存材料，不删难例/金标/阈值。

本次最终sql_capacity_measurements_final.json中1和10000组件写入＋一次sidecar读都15条SQL；10k原文{measurements[1]['raw_bytes']}bytes，service写{measurements[1]['write_seconds']:.6f}s。本文件是最终受控局部观察：原探针写相同sql_capacity_measurements路径，复跑更新了此前742绿色计时辅助文件；742全部红log/XML与原97封存完全未动。没有冒称旧绿色计时文件有第二份精确raw。循环/字典/栈加排序的复杂度与恒定SQL由源码及实际计数交叉，有限重复解析不是每组件数据库调用。此不证明P3问答SLA、并发吞吐或产品live。

本次自己的最终CBM src项目r11-sbom-review1-fix1-final-src-20261016为1509nodes/7879edges，默认排除assets；补独立assets项目r11-sbom-review1-fix1-final-assets-20261016，parse_partial/unusable均0，schema/architecture与资格名8trace实际执行并解析。rg确认嵌套路由caller，图0caller不视为无调用：HTTP当前user/permission→同Session InventoryService→parse_inventory_input/既有parser→raw/sidecar/current→change/epoch/outbox/receipt，返回safe snapshot；四读取与sidecar按认证tenant读冻结payload并做安全view。没有用742图证明6942。

**封存、隐私和范围**

共享backend/tests/conftest hook实际加载到独占副本/外目录probe，fixture显式登记动态合成值；失败正文和SQL/DEBUG sections写前脱敏，真实DSN/口令从内存捕获，不入argv/报告。最终seal还对实际参考值及所有fresh DB对应URL/口令做解压bytes扫描，另做shape检查，结果见seal_receipt；不是只跑regex。原pytest自动参数ID会在原24 XML的三种URI case和新followup四种encoded key case名中带明确合成fixture值；仅这些精确testcase metadata按源断言分类，失败正文/响应/DEBUG不豁免，真实配置值整文件扫描不豁免。742首红中的Engine表示有共享hook替换driver片段且口令是三颗星，按精确形状hash及两个原red文件分类，不将任意DSN豁免。它们是保留旧raw证据的合成用例名或已遮口令表示，不是产品日志凭据、实际URI回显或跨租户泄漏。源码/probe/harness与执行版gzip的显式合成输入或匹配器常量另标controlled source。没有删除或改写旧红XML来骗scan0。

封存工具前两次exit1单列：第一次本审遗漏UTF8参数被Windows默认GBK拒绝；第二次实际值匹配0，但形状分类器遗漏上述masked Engine及执行版gzip来源。修本审编码/精确分类后实扫通过，未改变失败内容或产品出站规则。两次工具原stdout只有会话记录，没有磁盘完整起止日志，不补造。最终收据给出实际上海秒级起止及精确扫描数量。

报告精确UTF8 raw copy为report_raw.md.gz；本run局部.gitattributes仅保护本审raw/log/XML，不改共享或全局attributes。日志签实际落盘bytes，Windows子进程stdout本身可能已有CR/CRLF，capture后redact/write_bytes不宣称原终端字节未转换。source blobs使用Git LF bytes并分列raw工作树hash；本审filelist/hash与control文件由manifest/seal可复核。复核只新增本报告和独占run，scope_diff证据确认业务/原tests/docs/contracts/progress/schema/migration/locks/frontend均无工作树修改。

第三方“安全展示”声明限定批准profile内的受保护定位/引用/PURL，不给任意自由文字含秘密作通用保证；external URI不访问，无网络来源/模型/FOFA/收费调用。没有生产环境/真实资产完整性或第三方标准全生态支持结论。

评分证据限F2/F3库存来源追溯与历史/变化发布、E1租户事务与类型/合同/安全边界、D1冻结复验材料；P2仅功能，不给盲测准确率，P3仅局部合成容量。原T24 C06本次发现已关闭，但整T24六条件及T28研判/OpenVEX/下游消费不由此签收。unit/contract/security与backend PG integration passed；frontend/e2e/live/manual、生产0022/default app装配、SBOM browser实际运行均not_run。另agent的新0022/正式装配SHA及119PG/371自检不属于5be本审结论。

Verdict: 有限Ship，本批无未关闭Must。下一步由主控用独立正式app/生产迁移/frontend/browser与live/manual证据处理剩余验收，不修改本审分母或把HTTPfixture替代live。
"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes(report.encode())
    (RUN / "report_raw.md.gz").write_bytes(gzip.compress(REPORT.read_bytes(), mtime=0))
    (RUN / "review_report_write_receipt.json").write_bytes(json.dumps({"time": now(), "path": str(REPORT), "sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(), "bytes": len(REPORT.read_bytes())}, indent=2).encode())
    print(json.dumps({"report": str(REPORT), "sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(), "bytes": len(REPORT.read_bytes())}))


if __name__ == "__main__":
    main()
