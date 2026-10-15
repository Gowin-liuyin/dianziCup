"""Create this author's report from the sealed real commands without acceptance claims."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
ZONE = timezone(timedelta(hours=8))

TEXT = """# R06-B · 仓库发布与社区正文适配

文档首次创建时间：{{start}}
本次写作开始时间：{{start}}
本次写作结束时间：{{end}}
最后更新时间：{{end}}
本报告证据截止时间：{{end}}
主控：/root；实现 Agent：/root/r06_repository_community_adapters
工作分支：codex/r06-repository-community-adapters
工作目录：D:/wt/r06-repos；基线：1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc
候选代码 SHA：e5b48ae4db4c1e77a08d830ce12eb63ab3d49c39
代码 tree：ac960dc28edf3d4c058b3b7b1d43566b2cf3145e
作者状态：awaiting_review；本切片实现：complete；整张 R06：partial，不能据此签 accepted。
独立审查：待主控新建 reviewer；本作者未作验收签字，也未 push。
验证层级：unit passed、contract passed、相关 security passed；integration/frontend/e2e/产品 live/manual not_run。

## 1. 输入输出与边界

范围为主控批准的 R06-B 对应 T11、T13 内部切片；R04 的证据/原文/网络底座可复用，R05 问答是否通过不影响纯适配。读取 AGENTS、执行地图、R06、T11、T13、03/04/05/06/07 合同和当前状态/交接；旧 accepted 记录未当作真实能力证明。用户外部材料仍仅作资料。

- `parse_github_releases(bytes) -> tuple[RepositoryRecord, ...]` 仅固定 `ollama/ollama` release 页。数值 release id 的命名空间标识稳定；tag/name 变化不改变身份，target_commitish=main 不成为 commit SHA。draft/prerelease/body/日期/固定域路径有严格类型校验，原始页完整留档；release 文本出现安全关键词不生成漏洞确认或修复结论。
- `normalize_avid_vulnerability(bytes) -> CommunityArticle` 只处理本轮实际取得的 AVID 0.2 形态。目录、未知版本、坏引用显式失败；metadata.vuln_id 为文章身份，问题标题和 description 文本分立。已识别 CVE/GHSA/AVID 引用按源 URL 的严格模式逐条保留，重复引用去重但不同漏洞不合并。自由文本标签不凭关键词转成漏洞身份。
- OSV `AffectedPackage.range_branches` 新增默认空 typed tuple，逐一保存 range_type/repository_uri/events/unsupported_scheme。原 `ranges_type`（末分支）及扁平 `events` 为兼容旧调用方保留，资产版本逻辑必须改用逐分支输入；本切片不执行版本比较。raw_record 完整保留。

仅修改来源模块与新测试；未改 source_jobs/source_documents、公共 schema、迁移、配置、依赖锁、进度、金标、阈值或评分分母。旧 T11/T13 所有六案例保留并复跑。R06 持續采集、游标/事务、八类产品能力和 T13 后续 R07 富化并未完成。

## 2. 复用、必要新增和调用方

按 Ponytail 5.2 full 使用已有 `strict_json_object`、`normalize_repository_record`、`normalize_community_article` 与 `NetworkGateway`；日期、URL、正则、hash/base64、压缩只用标准库。没有新增依赖、状态数据库、通用基类或 CRUD 框架。

新增两个源专属纯适配模块是实际 JSON 与原有预整形 DTO 的必要转换；OSV 原实现会把 package/event 坏类型强转为字符串，且不同 range 被扁平化，必须在同一共享函数修复。正常标识、旧 DTO 默认值与旧测试合同保持兼容；错误类型继续 RepositoryFetchError/OsvContractError，坏记录不以空列表或静默 skip 假成功。未知生态名及未知 range/event 保存原值；未知 boundary 标 unsupported，支持官方已有 limit 边界但不推导资产判断；缺日期仍 None，withdrawn 只有合法有时区字符串才成立。

初始 CBM 项目 `dianzi_r06_repos_1ff5496`：1085 节点/5218 边；源码图中三个既有 normalizer 无产品入边，rg 全 src/tests 核对到 T11/T13 合同测试。候选 CBM 项目 `dianzi_r06_repos_e5b48ae`：1103 节点/5321 边，0 not_indexed/partial/unusable；normalize_repository_record 与 normalize_community_article 分别增加本适配器的唯一源码 caller。normalize_osv_record 在当前 src 仍无产品 caller。图有/无边不独立证明业务正确，已和源码、rg、真实离线测试交叉核对。

索引范围仅 `/mnt/d/wt/r06-repos/backend/src`，缓存 `/tmp/dianzi-cbm-r06-repos-20261015`，CLI 官方 portable 0.11.0；未索引秘密、附件或 holdout，也未提交缓存。原始 index/schema/architecture/trace 与 `caller_frozen_rg.log` 在 run 目录。公共接线由主控的另一 worktree 统一修改，本作者没有扩张文件所有权。

## 3. 真实公开探测与来源样本

本批授权至多 4 GET，实际 3 GET、3 HTTP 200，Windows 原生 WТ 经现有 Gateway/cloudflare_doh；固定 GitHub AVID 2023 contents 列表后仅读取响应中的两个 40hex git blob。每次 15s/2MiB、总最迟90s、0 redirect、0 retry、单并发、起始间隔不少于7s；不跟 download_url，不读密钥/env/DPAPI，不取外部 reference，不执行材料。原响应 Header Date 为 UTC；人读起止时间均 +08:00。

{{probes}}

公开配额 Header 原样留存，三次 Remaining=59/58/57、limit=60；三源共用匿名池规则由主控统一实现，此 probe 不声称完整限流调度。429 或非200停止，不重刷。AVID 仓库许可依据已审准备包为 MIT，引用第三方材料仅原始记录内部证据留档，不推断第三方原作全量再分发许可。

`avid_02.record.json` 为 AVID-2023-V001，2195 bytes，sha256 `5fb9c019fe2aed64302b2182b2c297f499a3201349ce3c252acd4a409c096667`，固定 git blob `00fb8988850933aa6b17933990a5a02bdc26f828`。
`avid_03.record.json` 为 AVID-2023-V002，2497 bytes，sha256 `adf28092a120e1e584b2195428629f56824db4085fb6f88e7179e4400577f65b`，固定 git blob `5e9419c9bfce72868a5e9ea32314d6fbae293f72`。
解码后按 Git blob 头+字节重新计算 SHA1 与 API SHA 相等；目录 discovery 用浮动 main，但这两份正文按 blob 固定，不把 main 冒充 commit。目录响应本身不算社区正文。

两条 AVID published_date/last_modified_date 均为 2023-03-31，只有 date-only 精度；CommunityArticle 没有日期字段，因此原文保留、格式校验，但不能补午夜或 claiming current。当前真实记录 references 是 MITRE/论文/代码元数据，未识别成 CVE/GHSA，空已识别列表不等于无风险。DTO 未覆盖的 artifacts/impact/reports 与所有原始 references 仍在原字节，主控持久化不能只存 DTO 丢原文。

Ollama release 和 OSV 原始字节来自已审准备包，逐 byte Copy-Item 并验原 metadata sha256，无新增这两个源的网络调用。release 数值 id=413093320，tag=v0.40.5-rc0、name=v0.40.5、prerelease=true，不能把显示 name 误作正式稳定版。OSV GHSA-fccc-8m69-8r78 实际 aliases 为 CVE-2025-0315 与 GO-2025-3557，SEMVER 范围 last_affected=0.3.14，modified 纳秒字符串完整保留。上述均为离线真实响应合同核验，尚未 PG/worker/UI 产品 live。

OSV minor/patch 扩展按官方兼容原则保留未知字段，拒未知 major/错误版本形态；本候选只解析稳定的 1.x.y，不声称支持未确认 prerelease schema。limit 是官方已有边界；原始 schema_version 留 raw。依据：[OSV schema 官方正文](https://ossf.github.io/osv-schema/)，本轮核对当前 1.9.2，未知字段不会被资产判断擅自解释。

## 4. 问题与修复

| ID | 触发输入、预期与实际根因 | 影响/处理与复验 |
|---|---|---|
| R06-B-01 | commit 为40个 z/空格/NUL；预期拒绝，基线仅检查长度导致接受 | T13-C03 身份不可靠；改 fullmatch 40hex；红例15失败中的3条→候选通过 |
| R06-B-02 | 同一 affected package 内 SEMVER+GIT 两分支；基线只剩末个 type 且 events 混合 | T11-C03 分支丢失；新增 PackageRange tuple，repo/事件/unsupported 逐分支保存，兼容字段未删；新负例及原 T11-C01–06 通过 |
| R06-B-03 | aliases字符串、package生态数字、boundary数字、withdrawn=false、modified对象、NaN/NUL/未知major | 基线部分强转/忽略为默认成功；严格类型/有界 JSON 与日期校验；未知 scheme 仍保留 unsupported；整批坏条目失败 |
| R06-B-04 | 查询列表第二条 None | 基线列表推导静默跳过；_objects 有界验证整批报 OsvContractError，未变为空结果 |
| R06-B-05 | pytest 默认把2MiB bytes参数做node id，Windows PYTEST_CURRENT_TEST 超32767字符 | 首次候选6 setup/teardown错误属测试夹具命名；改短显式参数 IDs，保留全部恶意输入与原失败日志，不 skip |
| R06-B-06 | 作者首次把 release title 猜成 tag、OSV aliases/范围预期写成另一事件 | 两条离线真实样本断言失败；重新检查保存原始字节：name=v0.40.5，aliases=CVE-2025-0315/GO-2025-3557，type=SEMVER；纠正本切片开发断言并复跑，未改正式金标/分母 |

R06-B-01/02/03 在2026-10-15T18:24:48+08:00–2026-10-15T18:24:59+08:00红例复现；作者修复归入 e5b48ae。R06-B-05/06 在2026-10-15T18:29:31+08:00–2026-10-15T18:30:08+08:00首次候选暴露，2026-10-15T18:31:11+08:00–2026-10-15T18:31:44+08:00复验关闭为作者自检待独立复核。R06-B-04 在最终自检新增负例，source_security_regression 通过。独立 reviewer 尚未复核，不能写验收关闭。

首轮红例18项：15 fail/3 pass、coverage4.82<60、exit1。第一次候选1106次测试记录（含setup/teardown错误）：1098 pass/2 fail/6 error，coverage68.05、exit1；Junit testcase数量与testsuite tests含teardown不同，保留原XML不美化。无失败转 skip。

大失败日志原文17,016,093bytes与原JUnit4,484,295bytes继续留在作者 WT，提交 lossless .gz：`lossless_failure_archives.json`记录原文/归档双hash与尺寸，解压字节相等，未删/删改失败正文。

## 5. 实际命令与六类检查

下表每条工作目录 D:/wt/r06-repos/backend，Python/工具来自工作区外 D:/dianzi-runtime-cache/r06-repository-community/venv（uv sync --frozen，无lock改动）。精确argv、cwd、起止、exit见对应 `.command.json`；日志同label `.log`，两份巨型初次失败日志见 `.gz`。候选测试在业务内容冻结前运行，之后只提交同一 src/tests 内容为 e5b48ae，未再改业务代码；源码/测试9文件 diff --cached --check exit0，公开pattern扫描9文件0匹配。该扫描不代替主控实际秘密逐值扫描。

{{commands}}

最终自动验收：1212 pass、0 fail、0 error、0 skip =1089 unit +15 contract（原T11六项、T13六项、真实样本三项）+108相关network security。原cov60门保留，70.83%（6822 statements/1990 missed）；纯unit+合同1104 pass、68.08%。全src mypy84文件0问题，Ruff与format9文件通过。唯一Warning是已有 StarletteDeprecationWarning，非本模块行为失败，未新增忽略或改依赖。

六类可观察案例：C01真实三源字节和稳定标识；C02缺body/日期、schema和类型冲突；C03重复解析同id、tag修订不换身份（PG并发/宕机未测）；C04多range分支及unknown scheme/limit/原始纳秒；C05duplicate/NaN/NUL/surrogate/bytes/depth/node/恶意URL/records限额；C06坏第二条记录整批失败、PoC/关键词仅元数据且无执行路径。原T13权限/404历史案例与network transport预算/域/超时案例复跑，但真实新源权限/429/分页/重启/持续时效不声称已测。

## 6. 文件清单、差异与明确限制

业务4文件：新 github_releases.py、avid_records.py；定向修改 osv.py、repository.py。测试5文件：test_r06_osv_range_boundaries.py、test_r06_repository_commit_identifiers.py、test_r06_github_release_adapter.py、test_r06_avid_record_adapter.py、test_r06_repository_source_samples.py。报告此文件与独立 run 目录；没有用户既有文件/附件纳入提交。

没有新增公共合同/基础设施/评分变更。range_branches 的兼容追加及两个函数签名来自主控冻结授权。库函数只返回 typed input，不对 Claim/Assessment 写入；PostgreSQL 仍唯一权威，未用内存库换真实采集。没有付费模型/测绘调用；公开API具体费用 unknown。

尚未证明：两源产品接线、SourceKind配置/注册、PG raw→revision→outbox/page cursor事务、分页/漏采参考集、停机回补、持续监测完整周期、前端/e2e、性能/正式评测/人工核验。新DTO暂缺时间精度及release flags/body/canonical uri，因此主控必须同时保留和读取原文，不能只存DTO或把date-only填午夜、name当稳定版本。未知AVID形态/版本明确拒绝；只识别少量严格引用URL模式，其他原始引用仍保存，不靠模型/自由文本自动合并事件。仅保留无自动执行能力的材料；引用存在不代表支持关系已确认、PoC链接不代表执行成功。

## 7. 下一步

主控对含代码/样本/日志的最终固定 commit 派新独立 reviewer，复跑本表关键命令与源码链。通过后才集成到唯一source worker/PG/UI；本切片不能代替R06、T11、T13整卡或G-C阶段验收。R11需要逐branch语义比较，R07需要原始引用/事实富化，外部失败/日期精度由统一注册与业务持久化合同处理。未 push，未触碰用户主控 checkout/进度。
"""


def main() -> int:
    path = WORKTREE / "reports/tasks/R06-repository-community.md"
    if path.exists():
        raise RuntimeError("Author report already exists")
    started = datetime.now(ZONE).isoformat(timespec="seconds")
    probes = json.loads((RUN / "avid_probe_summary.json").read_bytes())
    probe_rows = ["| 请求 | 实际起止 | HTTP/bytes |", "|---|---|---|"]
    for index, probe in enumerate(probes, 1):
        probe_rows.append(
            f"| avid_{index:02} | {probe['started_at']} / {probe['ended_at']} | "
            f"{probe['status']} / {probe['size_bytes']} |"
        )
    command_rows = ["| label | 实际起止 | exit |", "|---|---|---|"]
    for label in (
        "baseline_boundary_red", "focused_post_implementation", "focused_recheck",
        "source_security_regression", "static_mypy", "static_mypy_final",
        "static_ruff_initial", "static_ruff_recheck", "static_format_recheck",
    ):
        record = json.loads((RUN / f"{label}.command.json").read_bytes())
        command_rows.append(
            f"| {label} | {record['started_at']} / {record['ended_at']} | {record['exit_code']} |"
        )
    ended = datetime.now(ZONE).isoformat(timespec="seconds")
    content = (
        TEXT.replace("{{start}}", started)
        .replace("{{end}}", ended)
        .replace("{{probes}}", "\n".join(probe_rows))
        .replace("{{commands}}", "\n".join(command_rows))
    )
    path.write_text(content, encoding="utf-8")
    print(json.dumps({"report": str(path), "started_at": started, "ended_at": ended}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
