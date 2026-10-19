from pathlib import Path
from collections import defaultdict, deque
import json
import re
import hashlib
from pypdf import PdfReader

B=Path(__file__).resolve().parent
R=B.parent
O=R/'deliverables'
m=json.loads((B/'report-map.json').read_text(encoding='utf-8'))
a=json.loads((B/'report-audit.json').read_text(encoding='utf-8'))
assets=json.loads((B/'asset-audit.json').read_text(encoding='utf-8'))
pages=json.loads((B/'word-pages.json').read_text(encoding='utf-8-sig'))
starts={x['text']:x['page'] for x in pages if x['text'].startswith(('第','附录 ','参考文献','概述'))}
pdf=PdfReader(B/'report.pdf')
lines=['# ShaoWang 报告重写交付说明','',
 '任务编号：REPORT-REWRITE-20261016（本次附件文档任务）；状态：`awaiting_review`。文档制作已完成，项目业务能力的待测项保持待测，不表示赛题验收通过。','',
 '## 1. 交付文件与改动摘要','',
 f'- `ShaoWang-技术报告.docx`：Word 实际排版 {len(pdf.pages)} 页；六章正文、40 条参考文献、附录 A–G；自动目录、图目录、表目录已经 Word 更新。',
 '- `ShaoWang-图源.pptx`：30 页，第一页为样式母版，其余为 29 张 F 图；F-28 按要求不绘制。',
 '- `fig/`：29 组同名 PNG／PDF，共 58 个文件；PNG 2400 × 1680，384 dpi；PDF 为 PowerPoint 原生对象导出的矢量页。',
 '- 全文按问题、做法、取舍组织；将来源连通性、Quake 语法校准与尚未测量的系统性能分开；不把配置文件、参考代码或截图占位当作已实现证据。',
 '- 全部 17 张 T 表为 Word 原生三线表；另有 12 张附录台账表。6 段参考代码共 101 行，与旧报告 CodeText 内容逐行一致。',
 '- 9 处截图沿用灰色占位，F-28 留黄底文字。原回填清单 74 处待测逐项对应；#9、#75 写为 D18 实测叙述。新增实录占位明确列出。',
 '- 作品正文按章重新编号；附录按 A-1 等编号。文献按正文首次引用重新连续编号，来源仅限 D21。',
 '- 只写入本次输出目录，未修改项目实现、冻结合同、全局任务状态，未提交或推送 Git。','',
 '### 篇幅与页码','', '| 部分 | 实际起始页 |', '|---|---:|']
for title,page in starts.items(): lines.append(f'| {title} | {page} |')
body_start=starts['第一章 作品概述']; ref_start=starts['参考文献']; app_start=starts['附录 A 数据源连通性实测']
lines += ['',f'正文 {ref_start-body_start} 页（{body_start}–{ref_start-1}）；参考文献 {app_start-ref_start} 页；附录 {len(pdf.pages)-app_start+1} 页。页码基于本次 Microsoft Word 排版；其他机器字体、打印驱动变化后应再次全选更新域。','',
 '## 2. 报告图号与原编号','', '| 报告图号 | F／S 编号 | 图题 | 位置 |', '|---|---|---|---|']
for f in m['figures']: lines.append(f"| {f['number']} | {f['id']} | {f['title']} | {f['location']} |")
lines += ['', 'F-28 无图源页、PNG 或 PDF，是按明确要求保留的例外。S-01–S-09 是截图占位，不纳入 F 图源交付。','',
 '## 3. 报告表号与原编号','', '| 报告表号 | 原编号 | 表题 | 位置 |','|---|---|---|---|']
for t in m['tables']: lines.append(f"| {t['number']} | {t['id']} | {t['title']} | {t['location']} |")
lines += ['', 'T-17 为可选字段特例表，本次已纳入；A-1 等是新增附录记录表，FAPP-1／FAPP-2 为生成脚本内部标识。','',
 '## 4. 全部占位清单','',
 f"按实际文档出现次序列出全部 {len(m['placeholders'])} 处：待测 {a['placeholder_counts']['待测']}、截图待补 9、图待补 1、实录待补 {a['placeholder_counts']['实录待补']}。表内位置精确到行、列，行号含表头。重复原文按出现顺序各占一行，不去重。",'',
 '原清单 #4–#6 从概述表改为概述叙述中的三处占位；#9、#75 分别位于 2.5.1 和 4.6.2，保留全球 172 411、中国 51 612、44／50＝88% 的记录，并区分 15:57 计数与 19:55 抽样（当时 172 401）两个快照。','']
checklist=(R/'source/astra-pack/backfill-checklist.md').read_text(encoding='utf-8')
queues=defaultdict(deque)
for line in checklist.split('## 二、')[0].splitlines():
    if re.match(r'\| \d+ \|',line):
        cells=[x.strip() for x in line.strip('|').split('|')]
        if int(cells[0]) not in [9,75]: queues[cells[-1]].append(cells[0])
lines += ['| 序号 | 原清单或新增标记 | 报告位置 | 占位原文 |','|---:|---|---|---|']
for i,p in enumerate(m['placeholders'],1):
    text=p['text']
    origin='#'+queues[text].popleft() if queues[text] else ('原截图清单' if text.startswith('【截图') else '原 F-28' if text.startswith('【图待补') else '新增（D18 表中待测）' if text=='【待测】' else '新增实录占位')
    lines.append(f"| {i} | {origin} | {p['location']} | {text.replace('|','／')} |")
assert not any(queues.values()),'Missing source placeholders'
lines += ['', '## 5. dossier 未展开或未作为完成证据使用的内容','',
 '- D8：报告保留工具契约、scope、长任务、三种客户端差异和 CLI 场景；未逐条复制完整配置命令。配置语法存在不等于完成调用，真实调用记录仍在附录 D 待补。',
 '- D9：公开 Schema、映射、沙箱和生命周期均有设计说明；未复制完整 manifest 与每个字段的接口字典。OSV、STIX、CSAF 没有原生承载项的字段须保留扩展或映射说明，未声称所有字段天然无损。',
 '- D10–D11：选型和 11 类实体及主要关系已入正文与图；未逐条展开全部数据库字段、索引和所有替代技术的接口细节。',
 '- D15：评测主协议、样本规模、对照、统计范围和台账均已保留；周计划和覆盖分组的完整执行表未原样复制为报告正文，执行细目仍以 dossier 为准。',
 '- D18：未把记录中的原始证据目录当作本次附件已提供的文件；不虚构终端输出、哈希、时长或客户端响应。附录 A、B、F 只据已有记录写初稿，其余保留可回填台账。',
 '- D21 的 40 条参考文献全部已引用；D22 的 F-01–F-30、T-01–T-17 均有报告位置，F-28 例外保留占位。','',
 '## 6. 建议补充与需核对的材料','',
 '以下是证据缺口或参考代码与设计文本的对应问题，不改动 D20 已裁决的口径：','',
 '1. 补交 D18 提到的境内原始日志及暴露面证据目录，登记时间、环境、请求标识、脱敏结果与 SHA-256；2026-10-14 的原终端输出未保存，应重跑并标记新日期。',
 '2. Hunter 首页 200／403 与业务 API 是不同入口；CNNVD 首页 200 不能证明数据接口可用；境外 arXiv RSS 200 不能证明境内 RSS 已通过。相关验证须分别补齐。',
 '3. C-05 只列若干 5xx，而设计写所有 5xx；带 Retry-After 的路径未展示统一 jitter；上限与抖动顺序、6 次是尝试总数还是额外重试数，需在最终实现合同中明确。代码按要求原样保留，未替作者修逻辑。',
 '4. C-06 默认 `standard` 与设计 `quick / deep` 不一致，参考节选未展示完整续取返回结构；需以最终接口合同统一。',
 '5. C-02 依赖未展示的生态解析与特殊 introduced=0 语义；需要边界用例和真实实现验证，不能仅凭节选宣布版本判断正确。',
 '6. D9 的无损映射表述需要明确扩展字段和未原生承载字段的往返规则；图及正文已避免将所有目标格式视为天然等价。',
 '7. D18 中 172 411 与 172 401 属于不同时刻；不合并、不平均，不将宽查询 823 690 当主展示的漏洞受影响数量。',
 '8. 问答引用、MCP 时延、自愈等仍有 xx 目标，需评审确认目标后再测；不得从本报告自动补成预期值。',
 '9. 九类来源不等于只有九个独立接口；截图待补原文中“9 个数据源状态灯”按清单保留，实际 UI 应明确类别聚合与底层来源对应。',
 '10. 红线中的 token 关键词与 D8 的 8k tokens、C-06 的 MAX_TOKENS 同时存在。本次保留必要技术术语与原代码，4 处关键词命中均非凭据，未用删除技术内容的方式制造关键词零命中。','',
 '## 7. 自检逐项结果','',
 '| 项目 | 结果与证据 |','|---|---|',
 '| 结构顺序 | 已按封面、摘要、Abstract、目录、概述、图表目录、六章、参考文献、附录 A–G 排列。 |',
 '| 概述 | 1 页，叙述覆盖架构、智能体、机制、选型、流程、实现、代码、展示、测试和创新十项；无“重要内容预览”。 |',
 '| 设计与创新对应 | 第二章按 D3–D13 展开；第五章七项分别指出第二、三章机制与第四章验证位置。 |',
 '| 数字来源 | 实测限 D18；背景案例和历史统计限 D1，设计阈值限 D2–D15；未新增观测。 |',
 '| 固定口径 | 9 类来源、9 维、9 角色、7 工具、8 Schema、3 扩展点、6 关联、5 时间戳、7 创新保持一致；6 h 仅漏洞首次发现。 |',
 '| 旧枚举 | TAGGED、RELATED_PAPER、AISI-、AISV-、三类实时通道、8 个 MCP 工具扫描均为 0。 |',
 '| 占位 | 74 项原待测逐项匹配，9 截图、1 图待补完整；新增 127 项（1 待测、126 实录）逐条登记；#9、#75 已测单列。 |',
 '| 敏感信息与 PoC | IPv4 正则 0；key/token/password 字面值赋值 0；4 处 token 技术词已人工区分。无攻击载荷、利用步骤或真实凭据。 |',
 '| 文献 | 40 条全部来自 D21；按首次引用编号 1–40；正文使用上标引用。题名、作者等未补写外部信息。 |',
 '| 禁用措辞 | 自动扫描所列套话命中 0，未使用营销式结果判断。 |',
 '| 段落抽查 | 1.1 案例、2.4.3 合并、2.5.3 裁决、2.6.2 引用、4.6.2 校准均有机制／参数／证据，非空泛评价。 |',
 '| 章节开头与代码说明 | 六章均有问题导向开头；无实验步骤模板或逐行解释代码；代码明确为参考节选。 |',
 '| 纸张与字体 | A4；沿用旧版左右 2.8／2.6 cm、上下 2.54 cm；正文宋体＋Times New Roman、12 pt、1.5 倍、首行 24 pt。 |',
 '| 题注与表格 | 图题下、表题上，SEQ 域连续；29 张 Word 原生三线表，无纵向格线，跨页重复表头。 |',
 '| 图源与导出 | 样式母版＋29 图，白底、指定配色与字体；29 PNG 均宽 2400 px／384 dpi，29 矢量 PDF 齐全。 |',
 '| 可编辑性 | 532 原生形状、136 连接线且首尾连接引用均齐全；图片对象 0；30 页备注齐全。 |',
 '| 图表对照 | 本说明第 2、3 节完整列出。 |',
 '| Word 域与分页 | 已由 Microsoft Word 更新全部域、目录与页码并导出审阅 PDF；完成全页排版检查。 |','',
 '检查边界：以上是文档与图源检查，不是软件单元测试、系统集成测试或外部 live 验收。真实模型、长期观测、客户端调用和故障注入未在本次文档任务运行。','',
 '## 8. 参考文献编号对应','', '| 报告编号 | D21 编号 |','|---:|---:|']
for ref in m['references']: lines.append(f"| {ref['number']} | {ref['dossier_number']} |")
lines += ['', '## 9. 复核与后续回填','',
 '正式送审前优先补齐截图、F-28 原始数据、连续运行统计、金标与问答对照、客户端只读调用与续取、故障注入日志；按本说明逐项回填，并同步摘要、概述、第四章与附录。文档状态仍为 awaiting_review，由评审确认后再改 accepted。','',
 '生成与验证脚本、PDF 审阅稿、逐页渲染和 JSON 审计留在交付包外的 `build/`，便于复核；交付包仅包含要求的正式文件。','',
 '### 文件校验值（SHA-256）','']
for name in ['ShaoWang-技术报告.docx','ShaoWang-图源.pptx']:
    lines.append(f'- `{name}`：`{hashlib.sha256((O/name).read_bytes()).hexdigest()}`')
(O/'交付说明.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(f'Wrote delivery notes: {len(m["placeholders"])} placeholders; {len(lines)} lines')
