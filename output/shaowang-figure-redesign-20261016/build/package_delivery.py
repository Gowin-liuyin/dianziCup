"""Write the handoff record and package the reviewed figure deliverables."""

import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DELIVERY = ROOT / "deliverables"
audit = json.loads((BUILD / "delivery-audit.json").read_text(encoding="utf-8"))
assert audit["status"] == "passed"
specs = json.loads(Path("D:/dianzi/output/shaowang-report-20261016/build/figures.json").read_text(encoding="utf-8"))
specs = [item for item in specs if item["id"] != "F-28"]
readme = """哨望报告配图重绘 — 使用说明

内容：29 页可编辑 PPT、29 张 2400×1680 PNG、29 页 PDF 预览。
PPT 每页对应一张报告配图。文字、图形、连接线均为原生对象；F-21、F-22 为原生表格。
编辑时使用 Microsoft YaHei（微软雅黑），可选择多个对象组合、移动、调整颜色或文字。
插入 Word 时，可直接使用 fig 目录内按图号命名的 PNG；修改 PPT 后可重新导出图片。
画布为 12.5×8.75 英寸，按技术报告配图比例制作，不是 16:9 答辩幻灯片。

设计参考：两份用户提供的优秀报告中的蓝绿黄语义分区与分层架构，以及蓝色立体图示模板中的层叠结构。
未覆盖原 Word；图中的设计目标、待测项、待核实项继续保留。
原清单的 F-28“各来源时延分布箱线图”要求由真实 CSV 生成，目前为图待补，本次不编造实测图。

图号 / 标题 / 报告位置
"""
readme += "\n".join(f"{item['id']} / {item['title']} / {item['location']}" for item in specs)
(DELIVERY / "使用说明与图号索引.txt").write_text(readme + "\n", encoding="utf-8-sig")
report = """任务编号：FIGURE-REDESIGN-20261016
任务状态：awaiting_review
实现状态：complete（29 张现有配图的重绘范围）

输入与范围
用户要求学习两份优秀报告的配色、构图，并参考蓝色立体图示模板，在 PPT 中重绘优化哨望技术报告配图。
输入 Word：D:/dianzi/output/shaowang-report-20261016/deliverables/ShaoWang-技术报告.docx
原始配图清单：D:/dianzi/output/shaowang-report-20261016/build/figures.json
参考 PDF 与模板的页码/图题清单见 build/source-inventory.json；渲染参考见 build/reference。
适用程序：已阅读 execution map、task_state、当前 T55 交接与其相关合同。本任务是独立配图交付，不推进编码任务卡。

改动文件
全部新增文件位于 D:/dianzi/output/shaowang-figure-redesign-20261016。
deliverables：ShaoWang-报告配图重绘.pptx、ShaoWang-配图预览.pdf、fig/F-*.png、使用说明与图号索引.txt、本报告。
build：redraw.mjs、render.ps1、finalize.mjs、audit_delivery.py、package_delivery.py、校验记录及参考分析。
本轮未修改原报告、源清单、业务代码、公共合同及全局 progress/task_state.json；没有提交、push 或发布。

实现内容
29 页、每页一图。蓝色为主，浅绿标识知识/通过结果，浅黄标识条件/目标，浅红标识失败或禁止。
架构使用分层立体面；时序、状态机、数据流、图谱关系按各自信息结构重排，保留原有技术标签和待测标记。
原生形状、文本与连接线；F-21、F-22 使用原生可编辑表格。PPT 内嵌栅格图片为 0。
F-28 原清单指定“由实测 CSV 用脚本生成（不是 PPT 手绘）”，原导出也未含该图，本轮保留待补。

实际命令与结果（工作目录 D:/dianzi；以下路径可直接复跑）
1. & 'C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'D:/dianzi/output/shaowang-figure-redesign-20261016/build/redraw.mjs'
   最终退出码 0；Created 29 editable figure slides。
2. & 'D:/dianzi/output/shaowang-figure-redesign-20261016/build/render.ps1'
   最终退出码 0；PowerPoint COM 导出 Rendered 29 slides，生成 PNG 和 PDF。
3. $env:RUNTIME_NODE_MODULES = 'C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
   & 'C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'D:/dianzi/output/shaowang-figure-redesign-20261016/build/finalize.mjs'
   最终退出码 0；结构与几何问题 0；29 页导入复核通过；800 处脚本字体使用微软雅黑。
   完整记录：build/finalize-command.log、build/pptx-validation.json。
   再次运行 finalizer 前需为新版本指定新输出路径或归档现有交付文件，避免覆盖冻结产物。
4. & 'C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' 'D:/dianzi/output/shaowang-figure-redesign-20261016/build/audit_delivery.py'
   最终退出码 0；74/74 项交付断言通过。记录：build/delivery-audit.json。
   验证图号覆盖、标题、原生对象、目标待测字样、PNG 分辨率、PDF 页数、最终文件与渲染输入一致、hash 和最后变更范围。
5. 目视检查所有 29 张 PowerPoint 导出的 PNG；修订后再次查看 F-01、F-04、F-24。
   可见内容比较确认，最终局部修改仅涉及以上 3 页，其余 26 页文本与几何未变。

修复与失败记录
早期探测缺少 fitz，退出码 1；使用已有 pypdf + Poppler 完成提取和参考渲染，无新增依赖。
早期参考提取因控制台 GBK 无法打印特殊字符失败，修正 UTF-8 输出后通过。
早期模板 COM 打开路径分隔符问题已修正为 Windows 路径。
首次字体校验出现 799 处问题：文本使用了不生效的字体属性；改为逐文本 run 的 typeface 后通过。
交付审计首次 69/73 项通过：检查脚本误把待补 F-28 算入现有导出，并比较了自动生成的 creationId。
修正为与原导出的 29 图清单逐项核对；仅排除两个生成型 creationId 元数据属性，保留全部文字与几何比较。
中间复跑 73/74 通过，定位剩余 p14:creationId 后修复；最终 74/74 通过。原失败保留在 build/audit-initial-failures.json。
原生表格无数值金额列，2 张表的算术检查标记 no_numeric_amounts，未计为业务测试通过。

验证状态与边界
unit：not_run（未改业务代码）；integration：not_run；live：not_run；manual：passed（逐页渲染图目视复核）。
artifact：passed。没有重新测试报告所描述系统的性能、准确率、在线能力和外部平台兼容性。
最终配图交付不存在外部阻塞；F-28 实测结果图仍依赖真实 CSV，不能作为已交付实测结果。

合同与计划偏差
无业务合同变更。仅对配图视觉表达重绘，不改变指标分母、事实、待测状态及安全边界。
沿用报告现有的 29 图范围，图号保留 F-01～F-27、F-29、F-30。

评分项证据
本产物提供文档与展示可读性证据；各图备注含报告位置和原 design-dossier 内容来源。
不能据此确认功能、性能、准确率或竞赛评分达标。

Git 与交接
开始分支 codex/full-delivery-recovery；开始 HEAD 68788632；交付前读取 HEAD 为 52b7143d6412935325ba344a92a61d31d7f9ddb8。
仓库存在既有及并发修改，本轮仅写上述输出目录，没有操作其他改动。
下一步建议：人工评审 PPT，确认后按图号将 PNG 插回报告；取得真实时延 CSV 后另行生成 F-28。
本任务停在 awaiting_review，不自行 accepted，不继续下一编码任务。
"""
report += f"\n最终 PPT SHA256：{audit['sha256']}\n"
(DELIVERY / "任务报告.txt").write_text(report, encoding="utf-8-sig")
state = {"task_id": "FIGURE-REDESIGN-20261016", "status": "awaiting_review", "implementation": "complete",
         "validation": {"unit": "not_run", "integration": "not_run", "live": "not_run", "manual": "passed", "artifact": "passed"},
         "figure_count": 29, "checks_passed": 74, "checks_total": 74,
         "out_of_scope_pending": "F-28 requires real measurement CSV", "final_pptx_sha256": audit["sha256"]}
(BUILD / "task_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
archive = ROOT / "ShaoWang-配图重绘交付包.zip"
with ZipFile(archive, "w", ZIP_DEFLATED) as output:
    for file in sorted(DELIVERY.rglob("*")):
        if file.is_file():
            output.write(file, file.relative_to(DELIVERY).as_posix())
with ZipFile(archive) as result:
    assert result.testzip() is None
    assert len(result.namelist()) == 33
print(json.dumps({"archive": str(archive), "files": 33, "bytes": archive.stat().st_size,
                  "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}, ensure_ascii=False))
