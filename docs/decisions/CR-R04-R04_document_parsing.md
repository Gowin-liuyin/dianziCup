# CR-R04 / R04 · 真实文档解析实施细则

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T12:20:17+08:00。作者/root，状态awaiting_review；落实用户批准R04/T09真实PDF和JSON字段定位，不改评分、盲测、金标和范围。

## 行为、兼容与迁移

pypdf6.20.1成熟组件替换pdf1测试TEXTLAYER标记，新增pdf2 parser版本；已有normalizer1 Unicode全局坐标不变，不重写旧revision/证据。新解析逐页保留页码，可靠文本缺失页不补OCR、不擅称扫描件；部分页有效记partial并逐页列缺口。加密/损坏/超限不伪造全文。JSON新json2保存RFC6901叶路径与原始Unicode值，重复键/NaN/Infinity/溢出/深度>32拒绝。旧json1片段依然读取旧revision，不用新规则覆盖历史。无数据库迁移，本批页码/路径进入实际数据库和API仍待R04后续，不能把内存ParseOutcome当整闭环。

## 资源、安全与依赖必要性

PDF在固定独立子程序经私有stdin/stdout解析，无外部程序/附件执行和URL请求；子环境只传运行必需键，不继承模型或数据库秘密。最多32MiB、300页、100万字符、同时2进程、20s墙钟；Linux地址空间512MiB/CPU15s，WindowsJob硬内存512MiB，限额不可用则拒绝。pypdf压缩流8MiB/累计32MiB/页面树深32/表单调用100，jbig2外部命令禁用。成熟库必要，不能再用测试标记或正则假PDF；小进程隔离为处理不可信PDF资源边界所需。官方[文本提取与内存说明](https://pypdf.readthedocs.io/en/latest/user/extract-text.html)、本机锁定6.20.1真实Configuration签名已核对。未做OCR、布局表格语义重建或图像识别，文本解析不声称这些能力。

## 回归与测试材料纠正

原T09-C01–C06及原门槛保留；C04旧输入仅%PDF假头+EOF本来不是有效扫描页，改为明确synthetic的真实1像素image-only PDF，仍要求unparseable/no reliable layer。新增损坏/假TEXTLAYER负例，不能继续把伪标记当真实文本。非人工金标/正式评测样本，未改阈值或分母。首次20 targeted通过；full unit+T09为255passed/cov61.10，60原门保持；本机真实600MiB分配在512MiB子进程中失败，official四页3882字符/页1–4/0.421s仅单次解析诊断不是问答指标。原始收据见reports/runs/recovery_r04_parsing_20261015；首静态发现长行与Windows分支resource类型推断问题，已格式化并用sys.platform Linux分支明确，最终Ruff和mypy64源码0。初步pytest --no-cov为targeted隔离，不是规避全量门；随后完整unit含coverage。

## 回滚、影响与验收

仅允许前向修复或停止新增解析并保留原始对象/版本；不得恢复生产接受TEXTLAYER假文本。未保存新证据前回退代码可用原版本读取历史，已保存新版本需继续保留pdf2/json2语义读取。影响T09/R04原文片段、R09资料和后续引用，必须经新独立review核对真正四页输入、缺页、边界、实际调用者及测试。此批仅awaiting_review，R04/T09/G-B未接受。
