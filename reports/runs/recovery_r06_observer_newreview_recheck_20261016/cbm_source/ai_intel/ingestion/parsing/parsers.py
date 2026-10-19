"""格式分立解析器: HTML 正文、结构化 JSON、PDF 文本各用独立逻辑, 不共用正则。"""

from __future__ import annotations

import json
import math
from html.parser import HTMLParser

from ai_intel.ingestion.parsing.pdf_text import PDF_PARSER_VERSION, parse_pdf_text_layer
from ai_intel.ingestion.parsing.text_blocks import ParseOutcome, build_blocks_from_segments

HTML_PARSER_VERSION = "html-1.0.0"
JSON_PARSER_VERSION = "json-2.0.0"

__all__ = [
    "PDF_PARSER_VERSION",
    "parse_html_document",
    "parse_json_document",
    "parse_pdf_text_layer",
]


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


def _unique_json_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        key.encode("utf-8")
        if "\x00" in key:
            raise ValueError("JSON key contains unsupported NUL")
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError("nonfinite JSON constant")


def _json_segments(
    value: object,
    pointer: str,
    depth: int,
    segments: list[tuple[str, str, int | None]],
) -> None:
    if depth > 32 or len(segments) >= 10_000:
        raise ValueError("JSON structural limit exceeded")
    if isinstance(value, dict) and value:
        for key, item in value.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            _json_segments(item, pointer + "/" + token, depth + 1, segments)
    elif isinstance(value, list) and value:
        for index, item in enumerate(value):
            _json_segments(item, pointer + "/" + str(index), depth + 1, segments)
    else:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("nonfinite JSON number")
        if isinstance(value, str):
            value.encode("utf-8")
            if "\x00" in value:
                raise ValueError("JSON string contains unsupported NUL")
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False, allow_nan=False)
        segments.append(("field:" + pointer, pointer + ": " + text, None))


def parse_json_document(content: bytes) -> ParseOutcome:
    """严格JSON叶字段按RFC6901定位；拒绝重复键、非有限数字和过深结构。"""
    if len(content) > 32 * 1024 * 1024:
        return ParseOutcome(
            status="unparseable",
            notes=("json input limit exceeded",),
            parser_version=JSON_PARSER_VERSION,
        )
    try:
        payload = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_unique_json_fields,
            parse_constant=_reject_json_constant,
        )
        segments: list[tuple[str, str, int | None]] = []
        _json_segments(payload, "", 0, segments)
    except (ValueError, UnicodeError, RecursionError):
        return ParseOutcome(
            status="unparseable", notes=("invalid json",), parser_version=JSON_PARSER_VERSION
        )
    return build_blocks_from_segments(segments, JSON_PARSER_VERSION)
