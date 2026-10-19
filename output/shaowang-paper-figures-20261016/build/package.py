from pathlib import Path
import json,hashlib
from zipfile import ZipFile,ZIP_DEFLATED
root=Path('D:/dianzi/output/shaowang-paper-figures-20261016');out=root/'deliverables'
readme='''ShaoWang 论文整图交付说明

使用方式
1. Word：插入 emf 文件夹中的对应文件，锁定纵横比，将宽度设置为 15.5 cm。29 张均为完整整图，不需要截图或逐块拼接。
2. LaTeX：使用 pdf 文件夹中的对应文件，例如 \\includegraphics[width=15.5cm]{F-01.pdf}。页面已裁去外部空白。
3. 继续编辑：打开 ShaoWang-论文整图可编辑.pptx。27 张示意图已组合，点击整图即可复制；需要编辑内部元素时取消组合。F-21、F-22 保留原生可编辑表格，在当前页 Ctrl+A 选择所有对象，或直接使用对应 EMF 整图。
4. PNG 为约 350–390 dpi 的裁边备用图，按 15.5 cm 宽度使用。优先使用矢量 EMF / PDF。

设计调整
删除演示用页眉和图号。图题由论文正文统一编号；PPT 备注保留图号、原题和报告位置。
沿用参考报告的蓝、浅绿、浅黄配色。时序图改用中文泳道名称，完整英文放在图例；两张关系图重新分配端口和标签位置。
按 15.5 cm 图宽检查，最小文字约 8.5 pt。若用于双栏论文，应优先跨双栏放置复杂图，缩到单栏前需另行简化布局。

包含 29 张，编号 F-01 至 F-27、F-29、F-30；F-28 沿用原报告的缺省范围。
“待测”“待核实”和示意占位均保留，未新增实测结论。
ShaoWang-论文版心插图样张.pdf：从原报告副本的 Word 实际导出中抽取 6 页，包含 7 张整图，说明原版心中的实际效果。原报告未覆盖。
'''
(out/'使用说明.txt').write_text(readme,encoding='utf-8')
audit=json.loads((root/'build/artifact-audit.json').read_text(encoding='utf-8'))
state={'task_id':'FIGURE-PAPER-REVISION-20261016','status':'awaiting_review','implementation':'complete','verification':{'unit':'not_run','integration':'not_run','live':'not_run','manual':'passed','artifact':'passed'},'artifact_checks':f"{audit['passed']}/{audit['total']}",'git_head_at_delivery':'9e6abcab95916340655f7dcdd163bf4cf851c7a4','scope':'Standalone paper figure revision. No repository business code, shared contracts, global task state, source Word or previous deliverables changed.'}
(root/'build/task_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
report='''任务：FIGURE-PAPER-REVISION-20261016
状态：awaiting_review；实现 complete；图件验证 passed；等待用户审阅。

本次改动范围：output/shaowang-paper-figures-20261016/。旧版交付、原始 Word、仓库业务代码、公共合同及 progress/task_state.json 均未修改。仓库存在其他会话修改，未提交或推送。当前分支 codex/full-delivery-recovery，交付时 HEAD 9e6abcab95916340655f7dcdd163bf4cf851c7a4。

实现：29 张论文整图；978 个原生形状、226 条连接线、2 个原生表格、27 个整图组合、0 张栅格化示意图。重排 F04/F14/F24，修正 F07 路线；移除演示页头；所有文字按 15.5 cm 宽度计算最小 8.5 pt。导出29组 EMF/PDF/PNG；29页裁边预览和6页原报告插入样张。

实际命令与结果（脚本均位于本目录 build）
Node redraw.mjs：退出0，29页可编辑PPT。
Python unlock.py：退出0。移除导出工具对自建形状写入的 noGrp 锁，以支持整图组合；不改变图形内容。
PowerShell export.ps1：最终退出0，29张PNG、29张EMF、27个组合及整套PDF。
Python crop.py：最终退出0，29张PNG和29份15.5 cm矢量PDF。
Node finalize.mjs：退出0；PPT结构、页面尺寸、字体策略、2个原生表格、第一方重新导入均通过，0条发现。750次字体脚本检查使用 Microsoft YaHei。
Python map-word.py：退出0，原Word中29张配图全部按内容散列匹配。
PowerShell word-proof.ps1：退出0，在副本中替换29张EMF，图宽15.5 cm；Word导出89页排版校样。
Python proof-sample.py：退出0，抽取并渲染6页实际插图样张。
Python audit.py：退出0，127/127项图件检查通过，详见 artifact-audit.json。
pdftoppm：退出0，PDF第24图矢量裁边复核。

失败与修复：最初PowerPoint组合失败，错误为“所选形状禁用组合”；更换Range选择方式未解决。随后检查最小复现及OOXML，确认根因是导出器写入noGrp=1；仅解除自建图元分组锁后成功。首轮裁边脚本深拷贝PDF对象过慢，人工中断退出1；改为逐页处理后退出0。上述均为图件工具问题，未计为业务测试失败。

目视检查：已检查29张PowerPoint实际渲染结果，并在修正后复查F04/F07/F24；6页Word实际插入样张（7张图）已检查。完整报告副本仅用于插图验证，未作为整篇重新排版后的正式交付。
未执行：业务unit、integration及live；本轮未测模型、来源、FOFA、性能或准确率。原数据和“待测”口径不变。原生表格无金额汇总，算术检查标记no_numeric_amounts，不算业务测试通过。

计划与合同偏差：从演示用配图修订为论文插图，属于用户最新明确要求。2页含原生表格不能与形状直接分组，保留表格编辑能力，并提供整张EMF/PDF用于迁移。没有修改项目冻结合同。
评分证据：支持文档配图及演示材料的可读性与可迁移性，不据此宣称系统功能验收或评分通过。
下一任务建议：用户按论文最终模板审阅；若版心或双栏宽度改变，再调整相应复杂图字号与布局。
'''
(root/'build/任务报告.txt').write_text(report,encoding='utf-8')
archive=root/'ShaoWang-论文整图交付包.zip'
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
 for p in sorted(out.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(out))
print('Packaged',archive.stat().st_size,'bytes')
