"""Write integration evidence while keeping stage acceptance and unknown timings explicit."""

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
common = f"""
## {started} · Root 默认调查工作台与 SDK 集成切片

本次写作开始时间：{started}
任务/阶段状态：in_progress；实现状态 partial；没有整卡或 G-E 验收。
Root 本批输入：reports/runs/recovery_reviewed_integration_20261016/reviewed_frontend_sdk_batch10_inputs.json。
已测源：26fa 产品底座加该精确输入与 Root App/nav diff；新候选代码 SHA 待 checkpoint 冻结，新默认入口独审尚未运行。

复用现有 AuthProvider/会话代际、EmptyState/错误状态、hash 导航、固定 revision 证据页面和动态 AmbientBackdrop；新增调查页面是持久调查 submit/read/cancel/operation receipt 的业务界面，新增 SDK typed models 是六工具冻结合同的投影。没有新前端依赖，SDK 保留已有包 metadata 与 Apache-2.0 文件。实际范围：anon 恢复裸调查导航及 UUID 路由不发私有请求；登录后的组件按服务端权限访问，慢响应经代际检查；证据 callback 包含 event/evidence/revision，禁止丢失历史修订号。

作者调查 source da43a8919a24119406b68fb16e1e3a344205d7c7 经新非作者 02c1c352c68b90737482decb821138c4d9fe92cc 限定 Ship；SDK 六工具 source 40b2d07bfd9047e38698339eb18a4f1e31a32153 经 e7213d6a786e118823101dac52d5549fe48ddad6 限定 Ship；models source 011ea225d18b7511a19d7d6056288f799bb83f20 经 336652179a2ba57937913ef83e1917287d6e2705 限定 Ship。Root 合并后独审需新 reviewer，组件结论不能代替新默认 PG/浏览器路径。

验证：frontend 60 文件/770 案例通过、0 skip，真实执行窗口见 frontend_batch10_unit.json，Vitest 48.18s；strict TS、ESLint、Vite build 全 exit0，输出 D:/dianzi-runtime-cache/root-investigation-ui-batch10-20261016。用户 tsconfig.tsbuildinfo SHA 3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d 每步检查相同，未 stage。

SDK 首次全收集在 base interpreter 不加载 pywin32.pth 时 15 collection errors/exit2/3.85s，未运行测试，原 sdk_batch10_unit.log/xml 保留。使用正常 venv 初始化复跑变动与相关 12 文件，474 passed、0 skip、7 record_property/JUnit 格式 warning，17.09s，exit0；sdk_batch10_related_fix1.json 提供实际命令/工作目录/开始结束与边界。package build/install、native cancellation、stdio 完整资源套件在本批 not_run，不能用 related 474 替代。

CBM 修改前独立 frontend/src 索引 1148 节点/5093 边、parse gap0，architecture/schema/Workbench trace 四命令 exit0；source snapshot 排除秘密/holdout/reports。Root App 改动后另用 batch10_post 缓存刷新，实际结果单列 receipts，不覆盖修改前日志。图与源码/rg交叉核验，旧任务占位页面与完整 R17 仍有缺口。

unit/contract/frontend：仅以上限定自动范围通过；integration/security/e2e/live/manual 本批 not_run。原组件 Edge 7/7 与修订错链负例只证明组件 fixture，未替代 Root 默认真实 PG/browser。当前公共 producer 独审剩一项声明引用不足的实证 Must，原作者 fix2 正修；tasks typed producer 仍 not_configured，风险 API/HTTP MCP/OAuth/三插件与完整平台接线待补。R16 历史/watch/retraction、R19 人工 gold、R20 旧 CPU/pipe 与秘密门尚未闭合，不能签阶段。

前端 JUnit XML 有一处 credential 形状，原件未提交、保留在工作目录；frontend_batch10_xml_withheld.json 仅保存整体 hash/精确偏移/匹配 hash，待独立 provenance 分类，不放宽扫描。Root 未运行新真实模型/外部来源，费用 unknown；fixtures 不计 live 或正式分母。

变更/限制：CR-R14/CR-R06 已 b578 正式冻结；CR-R16 completion/fanin 记录可选原子 guard、不可变父历史及 requested/effective 区分。无新公共评分/金标/阈值差异。本 checkpoint 只保存可审查候选与原失败，不计为阶段通过或 push。

下一步：新非作者 Root default PG/Edge 与六 SDK read routes 审查；接限定通过的 FD/source-mode 并验证默认模式注入；修 R14 unknown-stop 与 R18 声明支持，继续 R16/协议插件和真实六小时激活。
"""
for task_id, title in (("R17", "完整工作台"), ("R18", "REST、MCP、CLI、SDK 与插件")):
    path = ROOT / f"reports/tasks/{task_id}.md"
    previous = path.read_text(encoding="utf-8") if path.exists() else f"# {task_id} · {title}\n\n文档首次创建时间：{started}\n"
    path.write_text(previous + common, encoding="utf-8", newline="\n")
stage = ROOT / "reports/stages/recovery/G-E.md"
stage_body = stage.read_text(encoding="utf-8")
for label in ("本次写作开始时间", "本次写作结束时间", "最后更新时间", "本报告证据截止时间"):
    stage_body = re.sub(rf"(?m)^{label}：.*$", label + "：" + started, stage_body, count=1)
stage.write_text(stage_body + common, encoding="utf-8", newline="\n")
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
for relative in ("reports/tasks/R17.md", "reports/tasks/R18.md", "reports/stages/recovery/G-E.md"):
    path = ROOT / relative
    with path.open("a", encoding="utf-8", newline="\n") as document:
        document.write("\n本次写作结束时间：" + ended + "\n")
(RUN / "frontend_sdk_batch10_report_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": ended, "task_reports": ["reports/tasks/R17.md", "reports/tasks/R18.md"], "stage": "reports/stages/recovery/G-E.md", "stage_accepted": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"written_at": started, "stage_accepted": False}))
