"""格式分立解析器: HTML 正文、结构化 JSON、PDF 文本各用独立逻辑, 不共用正则。"""

from __future__ import annotations

import json
from html.parser import HTMLParser

from ai_intel.ingestion.parsing.text_blocks import ParseOutcome, build_blocks_from_segments

HTML_PARSER_VERSION = "html-1.0.0"
JSON_PARSER_VERSION = "json-1.0.0"
PDF_PARSER_VERSION = "pdf-1.0.0"


class _HtmlSegmentExtractor(HTMLParser):
    """HTML 结构化抽取: 标题/段落/列表/代码/表格行分立, 脚本样式内容剔除。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.segments: list[tuple[str, str, int | None]] = []
        self._current_type = "paragraph"
        self._buffer: list[str] = []
        self._suppressed_depth = 0
        self._table_header_pending = False

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in ("script", "style"):
            self._suppressed_depth += 1
            return
        if self._suppressed_depth:
            return
        self._flush()
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._current_type = "heading"
        elif tag == "li":
            self._current_type = "list_item"
        elif tag == "code" or tag == "pre":
            self._current_type = "code"
        elif tag == "th":
            self._current_type = "table_header"
            self._table_header_pending = True
        elif tag == "td":
            self._current_type = "table_row"
        else:
            self._current_type = "paragraph"

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._suppressed_depth:
            self._suppressed_depth -= 1
            return
        self._flush()

    def handle_data(self, data: str) -> None:
        if self._suppressed_depth:
            return
        self._buffer.append(data)

    def _flush(self) -> None:
        text = "".join(self._buffer).strip()
        self._buffer = []
        if text:
            self.segments.append((self._current_type, text, None))

    def close(self) -> None:
        self._flush()
        super().close()


def parse_html_document(content: bytes) -> ParseOutcome:
    """HTML 解析: 剔除脚本样式, 保留结构块; 空正文返回 unparseable。"""
    extractor = _HtmlSegmentExtractor()
    extractor.feed(content.decode("utf-8", errors="replace"))
    extractor.close()
    return build_blocks_from_segments(extractor.segments, HTML_PARSER_VERSION)


def parse_json_document(content: bytes) -> ParseOutcome:
    """结构化 JSON 解析: 字段成块; 非法 JSON 返回 unparseable 而非伪解析。"""
    try:
        payload = json.loads(content.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return ParseOutcome(
            status="unparseable", notes=("invalid json",), parser_version=JSON_PARSER_VERSION
        )
    segments: list[tuple[str, str, int | None]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            segments.append((f"field:{key}", f"{key}: {value}", None))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            segments.append(("list_item", f"{index}: {item}", None))
    else:
        segments.append(("value", str(payload), None))
    outcome = build_blocks_from_segments(segments, JSON_PARSER_VERSION)
    return outcome


def parse_pdf_text_layer(content: bytes) -> ParseOutcome:
    """PDF 文本层解析: 无可靠文本层(扫描页)返回 partial/unparseable, 不伪造全文。"""
    if not content.startswith(b"%PDF"):
        return ParseOutcome(
            status="unparseable", notes=("not a pdf",), parser_version=PDF_PARSER_VERSION
        )
    text_layer = [
        line.decode("utf-8", errors="replace")
        for line in content.splitlines()
        if line.startswith(b"TEXTLAYER:")
    ]
    if not text_layer:
        return ParseOutcome(
            status="unparseable",
            notes=("no reliable text layer (scanned page)",),
            parser_version=PDF_PARSER_VERSION,
        )
    segments: list[tuple[str, str, int | None]] = [
        ("paragraph", line.removeprefix("TEXTLAYER:"), 1) for line in text_layer
    ]
    outcome = build_blocks_from_segments(segments, PDF_PARSER_VERSION)
    return outcome
