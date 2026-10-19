"""Write final observed short document run and integrated regression facts, retaining earlier logs."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
target = root / "reports/tasks/R06-document-live.md"
assert not target.exists()
live = root / "reports/runs/recovery_r06_document_live_20261015"
end = json.loads((live / "runtime_end.json").read_text(encoding="utf-8-sig"))
assert end["reason"] == "owned_stop_request"
for mode in ("pure", "pg"):
    receipt = json.loads((Path(__file__).resolve().parent / f"main_0a45185_{mode}.json").read_text(encoding="utf-8-sig"))
    assert receipt["exit_code"] == 0 and receipt["head"] == "0a45185ae3ffb73a6d186b98421e26a52f78bfc6"
body = f"""# R06 · 资料页面真实链路与合并后回归

文档首次创建时间：{started}
本次写作开始时间：{started}
本次写作结束时间：WRITING_ENDED
最后更新时间：WRITING_ENDED
主控/root；限定实测证据 complete，整R06/G-C仍in_progress/partial。
工作分支codex/full-delivery-recovery；已测SHA0a45185ae3ffb73a6d186b98421e26a52f78bfc6；测试期间产品代码未修改。来源公共库/API/UI各自已有独立限定Ship，详情见R06报告；本实测新增证据尚待整阶段新reviewer，不自签accepted。G-C未push；远端最后核对G-B c229。

## 范围与真实结果

新专库test_dianzi_r06_documents_live_20261015，从空库前向到0015；原G-B持续观察库仍0014、未迁移。固定干净WT D:/wt/r06-document-live-0a45185，原文使用同受控MinIO，Redis13独立队列r06_document_live_0a45185。API28011/UI25174绑定loopback；4进程受Windows Job的512MiB/进程、2GiB总、20%host CPU、1200 CPU秒以及1200秒墙钟约束，40source jobs/120attempts/35秒执行watchdog/每日志16MiB。模型密钥从本段环境清空，允许模型调用0。

运行2026-10-15T21:01:51+08:00至21:16:10+08:00，实际859秒；主控stop.request正常受控结束，父级主动terminate令4子进程exit1，不能包装为各进程自然exit0。runtime_failure未产生；结束后28011/25174实际无监听。CPU29.765625秒/峰值677085184B为此段Job最后观测，非正式性能评测。

21:02:31至21:02:46，经真实PG会话/CSRF/API提交NVD与vLLM各1页：2真实HTTP200、30events、30documents、30revisions、143evidence、2page receipts/2fetch attempts。每个job attempt1，均partial/source_page_limit_reached，因为明确max_pages1；不是全部来源采集成功。job_runs包含beat框架记录，不能拿82当source jobs。旧2源writer metadata缺省，页面显示coverage unknown及未留存license，未认定全文。

21:05:16至21:05:25，真实Edge3pass/0fail/0skip，8.8秒；无route拦截，无fixture产品后备。1366与390实际登录→20+10分页共30唯一资料→当前详情→固定修订→永久证据/hash→刷新→paper筛选真实空结果→退出后deep-link不展示证据；原文publisher popup实际打开并核对URI。动态背景pointer-events none，reduced-motion下动画none，无横向溢出。新7source worker尚未合入，不能把本段证明算为9源live。

## 问题与更正

可视viewport截图是额外视觉QA，未增加3测试分母。首版capture脚本在检索后等待资料inspector，但正常检索会清除所选资料，实际TimeoutError；原capture-visible-initial.cjs、visible_capture-initial.log保留。只修脚本在结果中重新选中资料，13:14:57.874Z至13:15:00.388Z（UTC，上海21:14:57至21:15:00）成功取得1366/390 viewport截图，产品代码未改。长fullpage截图和两viewport均实际view_image核查。未把仪器错误包装成产品缺陷，也未把失败日志覆盖为通过。

## 实际命令与日志

工作目录均D:/dianzi，命令不含秘密参数；秘密只由既有私有配置与DPAPI注入进程，日志脱敏。

| 命令/阶段 | 起止+08 | exit/数量 | 原始证据 |
|---|---|---|---|
| live/launch.ps1 -Mode prepare/start | 见prepare_receipt/runtime_start | 成功，实际时刻按receipt | recovery_r06_document_live_20261015 |
| live/launch.ps1 -Mode collect | 21:02:31–21:02:46 | 0；2source jobs partial | collection_receipt.json |
| live/launch.ps1 -Mode browser | 21:05:16–21:05:25 | 0；3passed | browser_command.json、browser_report.json、browser.log |
| live/launch.ps1 -Mode preview初版 | 历史命令秒级起止未单独记录 | 1；TimeoutError | *initial.cjs、*initial.log |
| live/launch.ps1 -Mode preview修正版 | 21:14:57–21:15:00 | 0；2viewport、0overflow | visible_capture_receipt.json、document-visible-*.png |
| integration/check_integrated.py main_0a45185_pure pure | 21:15:52–21:17:18 | 0；1687passed/10real_pg deselected/0fail，74.74%保留60门 | main_0a45185_pure.json/xml/log |
| integration/check_integrated.py main_0a45185_pg pg | 21:15:52–21:16:35 | 0；41passed/0fail/0skip | main_0a45185_pg.json/xml/log |

live路径指reports/runs/recovery_r06_document_live_20261015，integration指reports/runs/recovery_r06_integration_20261015。真实PG41由catalog21+API20组成，独立UUID schema，显式专库，未运行任何降级；纯测试10real_pg明确交真实PG套件，未把失败改skip。1个Starlette/httpx弃用warning保留；不为消warning升级锁。

## 复用、限制与下一步

复用既有OwnedJob、真实worker/outbox/网关/MinIO、Cookie/CSRF、原来源API与页面组件；没有新增依赖或另建事实库。新增有界启动/采集/浏览器脚本只是验收所需，不进入产品模型上下文；登录密码、session cookie/CSRF未写截图或请求日志。精确秘密扫描覆盖本run文本与本报告，见secret_scan；主控尚需阶段提交前统一检查。

本段不是6小时稳定运行或及时/漏采正式指标。原1927六小时服务保持独立，不能拼时段或版本。人工标注/FOFA授权范围仍缺；正式评测、9新来源、九维/图谱/完整工作台未由此通过。下一步正常独立审查worker+admin UI，合入后同版本真实9源链路及R06余下调度/通道/观测，再推进G-C其余范围。
"""
ended = datetime.now(clock).isoformat(timespec="seconds")
target.write_text(body.replace("WRITING_ENDED", ended), encoding="utf-8")
note = f"\n\n{ended} /root补充真实结论：0a45185合并后1687pure/74.74%与41真实PG均exit0；资料短段21:01:51至21:16:10 owned_stop_request结束，4子进程被主动terminate exit1，无运行失败文件，端口无监听。新增报告R06-document-live.md保存完整命令/红例/3真实Edge与30文档143证据；整卡/阶段状态不变。\n"
for name in ("reports/tasks/R06.md", "reports/stages/recovery/G-C.md", "progress/context_handoff.md"):
    path = root / name
    path.write_text(path.read_text(encoding="utf-8-sig") + note, encoding="utf-8")
print(json.dumps({"created_at": started, "writing_ended_at": ended, "report": str(target), "whole_R06_accepted": False}))
