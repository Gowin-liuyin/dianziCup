# R04 · 真实PDF与JSON字段定位切片

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T12:20:17+08:00。作者root，awaiting_review/partial。合同见docs/decisions/CR-R04-R04_document_parsing.md。

旧PDF只识别TEXTLAYER，真实官方PDF无法抽取；现调用pypdf6.20.1固定受控子进程，真实4页3882字符和页码均留存，首诊断0.421s；无可靠文本/部分页/加密/坏格式/超限分别有固定状态与notes，不进行OCR。JSON json2支持严格重复键和RFC6901叶路径。复用TextBlock/normalizer1/既有EvidenceSpan定位和引用权限，无重写账本。

命令与结果在reports/runs/recovery_r04_parsing_20261015各receipt：first targeted20/20，full_unit255/255/cov61.10、Ruff0/mypy64files0。原T09-C04假PDF输入换为真实synthetic image-only PDF，原caseID/语义/断言保留并新增损坏输入，非金标改动。600MiB子分配实际MemoryError验证Windows硬限512MiB。原始首次静态失败和无效rootcwd mypy命令事实保留在工具记录（rootcwd未加载backend配置误报celerystub，backend正确cwd最终通过）；不把环境错误当产品缺陷。

代码自检期间根基底7f9，PDF文件归root独占；后续网络修复另切片，不以本次日志给新网络背书。尚无持久页码/API/来源worker装配或R04全e2e，live source not_run、frontend/e2e/manual本切片not_run，独立review待排。依赖新增pypdf68packages，说明性注释均docstring。

2026-10-15T12:34:18+08:00 · 新独立初审确认JSON两项Must：json.dumps使合法字符串换行/quote/backslash转义而无法原值EvidenceSpan定位；孤立surrogate误parsed导致UTF8保存失败。最小修复仅字符串叶保留解码原值、键/值严格UTF8且NUL显式拒绝，不改原始对象或旧revision，新增完整Unicode跨度与surrogate/NUL键值六案；补PDF子程序坏IPC/超时kill-drain/并发归还及秘密环境不继承八案。这些是实际边界回归，不调整阈值/分母。修复后纯unit268passed、原60门实际61.42%、mypy64files0；首次Ruff含0012测试四个SQL长行失败，换行不改SQL后ruff_final0，失败日志保留。先前f2纯unit248passed但59.98%不足60，pytest-cov6按默认precision0取整导致返回0而终端仍FAIL；独立报告应保持该门失败，不能把255含合同61.10冒称纯unit通过。当前原始实际61.42高于60，仍需独立新SHA复核；工具舍入问题登记R20 CI严格原始覆盖率门，不依赖退出码自绿。
