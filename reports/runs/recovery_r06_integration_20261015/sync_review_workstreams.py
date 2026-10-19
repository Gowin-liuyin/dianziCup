"""Register immutable independent reports and active preparation without granting stage acceptance."""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def copy_verified(source_root, relative, expected=None):
    source = source_root / relative
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if expected is not None:
        assert digest == expected.lower(), str(relative)
    target = root / relative
    assert target.resolve().is_relative_to(root.resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert target.read_bytes() == content, "do not overwrite prior evidence"
    else:
        shutil.copyfile(source, target)
    return digest


packages = [
    (Path("D:/wt/r06-source-admin-ui-review-1"), "recovery_r06_source_admin_ui_review_1_20261015", "artifact_manifest.json", "artifacts", "G-C-R06-source-admin-ui-review-1.md", "291703a3fceec671341db3963545c8917a1b9827cc44c7495b75b8a1fbe2cd03"),
    (Path("D:/wt/r06-source-worker-review-1"), "recovery_r06_source_worker_review_1_20261015", "evidence_manifest.json", "artifact_files", "G-C-R06-source-worker-review-1.md", "815e5bcc853f8c923e3e68acdd8913978399c9f90473989f27e6cf1902841d32"),
]
copied = []
for source_root, run_id, manifest_name, key, report_name, report_hash in packages:
    relative_manifest = Path("reports/runs") / run_id / manifest_name
    manifest = json.loads((source_root / relative_manifest).read_text(encoding="utf-8-sig"))
    for entry in manifest[key]:
        relative = Path(entry["path"])
        normalized = str(relative).replace("\\", "/")
        assert normalized.startswith("reports/runs/" + run_id + "/") or normalized == (
            "reports/reviews/recovery/" + report_name
        )
        copy_verified(source_root, relative, entry["sha256"])
    copy_verified(source_root, relative_manifest)
    copy_verified(source_root, Path("reports/reviews/recovery") / report_name, report_hash)
    copied.append({"report": report_name, "sha256": report_hash, "manifest_members": len(manifest[key])})


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


state_path = root / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
original_tasks = json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
for key, reason in [
    ("R19", "Authorized early preparation after accepted R04/G-B: annotation tooling and public dev candidate, no human gold or final freeze"),
    ("R20", "Early safety preparation: isolated Windows CPU guardian repair; full operations/security/CI and final gate remain unproved"),
]:
    item = state["recovery_tasks"][key]
    assert item["status"] in {"pending", "in_progress"}
    item.setdefault("history", []).append({"recorded_at": at, "prior_status": item["status"], "prior_implementation": item["implementation"], "event": reason})
    item["status"], item["implementation"] = "in_progress", "partial"
    assert all(value == "not_run" for value in item["verification"].values())
    item["verification_scope_notes"] = {"recorded_at": at, "current": reason + "; component checks cannot pass the whole R card or G-F"}
r06 = state["recovery_tasks"]["R06"]
for package in copied:
    reference = "reports/reviews/recovery/" + package["report"]
    if reference not in r06["evidence"]:
        r06["evidence"].append(reference)
r06["history"].append({"recorded_at": at, "prior_status": r06["status"], "prior_implementation": r06["implementation"], "event": "New source admin UI independently Ship, unmerged until backend alignment; normalizer/worker independent M1/M2 need repair; root fix 6dcce8b frozen self-check passed, independent recheck pending"})
assert r06["status"] == "in_progress" and r06["implementation"] == "partial"
r06["verification_scope_notes"] = {"recorded_at": at, "current": "Integrated documents actual Edge/PG passed; source UI and polling independently scoped Ship but unmerged; source boundary fix 6dcce8b awaiting targeted independent recheck; whole R06 and G-C incomplete"}
state["updated_at"], state["updated_by_task"] = at, "R06 independent review pipeline and authorized early R19/R20 preparation"
assert json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True) == original_tasks
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

snapshot = f"""## 当前权威快照 · {at}

主控codex/full-delivery-recovery HEAD0a45185ae3ffb73a6d186b98421e26a52f78bfc6；远端最后核对G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7，19:28:36+08。G-A/G-B限定accepted，G-C/R06 in_progress/partial未阶段push；原T全映射与整卡验收保持。主分支已合资料公共库/API/资料UI，合并1687pure74.74%/41真实PG与30真实资料143证据/实际Edge3pass已取得，报告R06-document-live.md。短段21:01:51–21:16:10 owned_stop_request已结束且端口28011/25174无监听，主动terminate子进程exit1不冒称自然0；不是6小时。

九来源管理UI代码4f00999c2834a14752f4d53a78ccac66abed5cab、材料6f38d4284e62820415d829c9f113193e9bfce1b0，全新r06_source_admin_ui_independent_review限定Ship；339unit/type/lint/build/独立Edge20(原8+新12)通过，报告291703a3...与51产物已核复制主库。尚未合入，以免main后台仍2key而UI暴露9key；待worker组合通过一并集成。

新增7source worker代码52433474f66a900c56ee6d5478337b0ec83d6eda、材料b2bd53fd2320fc46f600ff0475298ec1b64b0172在D:/wt/r06-worker-wiring；全新r06_source_worker_combined_independent_review已审root normalizer+worker全部组合，独立1760pure74.42%/91PG通过，但新19probes8红11绿，M1 CAC末条无正文仍full_text/succeeded、M2 OSV非法/未知/超精度时间提升UTC需修，报告815e5bcc...与56产物已核复制主库。代码未合main/新7live未运行。

root独占修复WT D:/wt/r06-source-boundaries-fix，基线b2bd，代码冻结6dcce8b115ee3cb68bce814cf3f3ae91be9fcbf1，4产品+2永久测试+CR-R06_source_timestamp_precision。CAC每条非空/最后生效句只在末条内校验；共享日期语法严格，非法+00:99 blocked；合法-00:00或>6小数保留raw、PGinstant NULL、precision unknown，不静默截断。首轮全拒高精度使实际OSV modified9位合法样本失败，原16红/43+1红保留；新兼容小合同需原reviewer定向核对，原NVD/vendor严格策略不变。1788pure74.52%和96PG自检通过；冻结后同两套复跑已exit0，准确数量/时刻见recovery_r06_source_boundaries_20261015；尚未独立复核/合并，不能据此过门。

自动轮询root WT D:/wt/r06-source-polling冻结93c458a0f97b65198d1fb690d42634b77342bb3c，8文件494+，source_polling/module+runtime/settings/compose开关+直接测试+合同/手册；真实部署flag显式开启才beat60s建固定9源PG/outbox，vLLM30min其余60min，每轮5页，复用原job/cursor，无迁移/新依赖。1777pure74.15%/10PG作者通过。全新r06_periodic_collection_independent_review在D:/wt/r06-source-polling-review-1审93，已17unit/10PG/24新边界/4runtime检查与实际默认60s beat→RedisDB15 prefix→PG→fixture worker通过，停用重启65s保留9root并完成手动任务。其共享mainvenv首次coverage52.19红确认双路径污染，own离线冻结venv1777/74.15%原60门通过；未降低门槛。阈值500为入场阈值，500单源active可本tick添8到508，下一tick拒绝，不能称硬cap500。独立报告G-C-R06-source-polling-review-1.md已限定Ship，sha1f1b31d2af6898bf41101f69e31f5094dd9c6a4ee52767922b0077a9cfdfe07e；82项产物待核复制，source live未运行。作者报告R06-source-polling.md/35run在其WT，meta尚未提交；root需修报告初版遗留静态working_tree标签说明再保全hash。

Windows native CPU guard原994c独立Must1: guardian ready后硬退出worker仍成功/CPU2.25s。作者修复代码852472810b20b113606a0275ae6861326d39ebe8、材料3c99f37ef1993ab677e0d21b9d080975524d44b4在D:/wt/native-cpu-guard，默认1054/67.19054%与原预算不变。原独立native_cpu_guard_independent_review已实际2次hardexit CPU0.484375/无WORK_COMPLETED，原20probe0timeout、父PDF/semantic故障/成功对照4项、32针对+1054pure通过，独立限定Ship，Must1关闭；复核报告G-C-native-cpu-guard-review-1-recheck.md sha72da5d4d9700a742c37db92b0aaf46f3cd82a87d440ba61420019ad1ca13ad6d及76产物已由reviewer复制主库待主控核验。kill-on-close可exit0，完整结果协议是成功边界；未合main，整R20仅early partial不签验收。

4槽：root控制合同/schema/锁/集成/状态/Git及source修复；r06_source_worker_combined_independent_review独立复核6dc；CPU及poller reviewer已完成释放槽位；r19_annotation_preparation独占D:/dianzi-r19-annotation-preparation（branch同名、基线0a）的新benchmarks候选schema/manifest、scripts/annotation、直接测试/单卡报告/手册。R19原合同允许R04后早工具/候选，当前仅公开vLLM短包、0人工金标，不读holdout答案/DPAPI或改指标；需后续全新review。R19/R20登记in_progress/partial仅真实早准备，八层整卡验证not_run；G-F没通过。当前宿主4硬槽，不能实际6–10。

实际网络补探4个固定官方入口21:22:30起：CNNVD200仅985B壳、CNVD521空、EPSS200/203B/1记录、CISA KEV200/1787354B/1745条，仅probe无产品富化/0模型。run recovery_r06_auxiliary_source_probe_20261015，原body仓外cache。随后正常浏览器CNNVD官网下载19页649246B官方XML接口PDF，sha805577874f0ea63e137b147b7728eb232f12a003a105db12b54bc5764b24377c；参数物理页10已render/view核查，PDF/提取原文仓外，不使用公开示例AppSecret。公开当天XML点下载明确要求先登录，API要求授权AppID/AppSecret；CNVD未绕过验证。异步最小问题已问CNNVD授权变量名/秘密管理注入，等待非阻断；没有请求或打印真实用户密钥。

原1927受控6小时服务保持独立19:45:24–次日01:45:24，API28010/Redis12/12轮30min；最后心跳与实际版本看recovery_gb_controlled_collection_20261015，不能拼不同版本。MinIO19:45:17–次日02:15:17/29400/WSL8440-8461；Docker总deadline2026-10-17T21:49:15。模型累计8次/fee unknown，本次0新增；双人独立金标/裁决与FOFA授权资产范围仍缺，PPT用户后置。下一步source6dc原reviewer定向复核、两新review报告封存→normalizer/worker/UI/poller/CPU修复审查闭合→main安全合入/组合回归→九源同SHA真实beat/API/UI→R06剩余通道/观测与G-C R07–R10；R24-A→R23→R24-B不变。

"""
for name in ("context_handoff.md", "recovery_workstreams.md", "blockers.md"):
    path = root / "progress" / name
    path.write_text(snapshot + path.read_text(encoding="utf-8-sig"), encoding="utf-8")
stage_path = root / "reports/stages/recovery/G-C.md"
stage = stage_path.read_text(encoding="utf-8-sig")
for prefix in ("本次写作开始时间：", "本次写作结束时间：", "最后更新时间：", "本报告证据截止时间："):
    stage = "\n".join(prefix + at if line.startswith(prefix) else line for line in stage.splitlines()) + "\n"
stage = stage.replace("## 2. 当前真实状态与修改\n", "## 2. 当前真实状态与修改\n\n" + snapshot + "以下为有时间戳的历史，不能覆盖当前快照。\n", 1)
stage += f"\n{at} /root修订：记录两次新独立结论、M1/M2修复流水线、真实调度审查及合法早准备；整卡/阶段未验收。\n"
stage_path.write_text(stage, encoding="utf-8")
(Path(__file__).resolve().parent / "review_sync_receipt.json").write_text(json.dumps({"at": at, "copied": copied, "original_T_unchanged": True, "R06": "in_progress/partial", "R19_R20": "early in_progress/partial"}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"at": at, "packages": len(copied), "original_T_unchanged": True}))
