# RV-T09 · T09 独立快审

结论：**T09 = accepted**

## 1. 复跑命令与退出码

| 命令 | 结果 | 退出码 |
|---|---|---|
| `uv run pytest tests/contract -q --cov-fail-under=0`（backend） | 7 passed（7/7，0.15s） | 0 |
| `uv run mypy src`（backend） | Success: no issues found in 24 source files | 0 |

## 2. 三断言抽查

① **HTML/JSON/PDF 三格式分立实现（非单正则共用）——通过。**
- HTML：`parsers.py:15-66` `_HtmlSegmentExtractor(HTMLParser)`，stdlib 结构化抽取（标题/列表/代码/表格/段落），无正则。
- JSON：`parsers.py:77-95`，`json.loads` + dict→field: 块 / list→list_item 块，独立分支。
- PDF：`parsers.py:98-119`，独立的文本层行抽取逻辑（无 TEXTLAYER 行即判定无可靠文本层）。
- 三路径仅共享 `text_blocks.build_blocks_from_segments`（块组装与偏移计算），解析逻辑各自独立，全文件无任何正则共用。

② **多处命中未给 block→AmbiguousQuoteError；扫描页→unparseable 不伪造全文——通过。**
- `evidence.py:48-52`：未给 block 时 `len(matches) > 1 or sum(block.text.count(quote)) > 1` 即抛 `AmbiguousQuoteError`，同时覆盖"跨块多命中"与"同块多次出现"，不随机匹配；给 block 后精确定位（C03 断言覆盖）。
- `parsers.py:109-114`：无文本层返回 `status="unparseable"`、`blocks=()`、note 含 "no reliable text layer (scanned page)"，不输出伪全文（C04 断言覆盖）；脚本-only 页同为 unparseable。

③ **跨租户片段 404 语义 + 脚本不进块——通过。**
- `evidence.py:64` `render_revision_snippet` 先 `scope.enforce_visible`，`access.py:75-78` 统一抛 `CrossTenantAccessError("resource not found")`，消息不泄露对象名称与存在性（404 语义，由 API 调用方转换为 HTTP 404）；C06 以 tenant-beta 访问 tenant-alpha 片段断言异常，属主片段原样返回。
- 脚本/样式：`parsers.py:27-31, 47-50, 53-56` `_suppressed_depth` 抑制 `script/style` 内容，C06 断言 `"alert" not in joined`。

## 3. 边界说明（不影响结论）

- PDF 文本层仅验证合成 `TEXTLAYER:` 结构，真实 PDF 语料 `not_run`（实现者已在 reports/tasks/T09.md §5 如实登记，非伪造）。
- 片段展示 HTTP 端点属后续 API 批（域语义已在 evidence 层验证），本次未查，`not_run`。

## 4. 未查项

- unit/integration/security 全量回归、ruff、真实语料 live：本次不在快审范围，`not_run`。
