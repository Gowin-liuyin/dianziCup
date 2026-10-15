"""Public recorded inputs plus explicit synthetic transport/PDF/pagination fixtures."""

import base64
import hashlib
import json
import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

ROOT = Path(__file__).resolve().parents[2]
FEEDS = ROOT / "reports/runs/recovery_r06_feed_parsers_20261015"
REPOSITORY = ROOT / "reports/runs/recovery_r06_repository_community_20261015"


def policy_without_article_body(ordinal: str) -> bytes:
    """Keep a real article heading and its following chapter, but remove its body."""
    original = (ROOT / "fixtures/recorded/cac_generative_ai_20261015_public.html").read_text(
        encoding="utf-8"
    )
    article = re.search(r"<strong>第" + ordinal + r"条</strong>", original)
    assert article is not None
    following = original[article.end() :]
    chapter = re.search(r"<p\b[^>]*>\s*<strong>第[一二三四五六七八九十]+章", following)
    assert chapter is not None
    assert (
        re.search(r"<strong>第[一二三四五六七八九十]+条</strong>", following[: chapter.start()])
        is None
    )
    return (original[: article.end()] + "</p>" + following[chapter.start() :]).encode()


def nist_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 700 Td (NIST AI 100-1 January 2023 fixture text) Tj ET")
    page[NameObject("/Contents")] = stream
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def avid_responses(*, two_records: bool = False) -> tuple[bytes, bytes]:
    record = (REPOSITORY / "avid_02.record.json").read_bytes()
    digest = hashlib.sha1(b"blob " + str(len(record)).encode() + b"\0" + record).hexdigest()
    entries = [
        {
            "path": "vulnerabilities/2023/AVID-2023-V001.json",
            "type": "blob",
            "sha": digest,
            "size": len(record),
        }
    ]
    if two_records:
        second = record.replace(b"AVID-2023-V001", b"AVID-2023-V000")
        second_digest = hashlib.sha1(
            b"blob " + str(len(second)).encode() + b"\0" + second
        ).hexdigest()
        entries.append(
            {
                "path": "vulnerabilities/2023/AVID-2023-V000.json",
                "type": "blob",
                "sha": second_digest,
                "size": len(second),
            }
        )
    tree = json.dumps({"sha": "a" * 40, "truncated": False, "tree": entries}).encode()
    blob = json.dumps(
        {
            "sha": digest,
            "encoding": "base64",
            "size": len(record),
            "content": base64.b64encode(record).decode(),
        }
    ).encode()
    return tree, blob


def avid_second_blob() -> bytes:
    record = (
        (REPOSITORY / "avid_02.record.json")
        .read_bytes()
        .replace(b"AVID-2023-V001", b"AVID-2023-V000")
    )
    digest = hashlib.sha1(b"blob " + str(len(record)).encode() + b"\0" + record).hexdigest()
    return json.dumps(
        {
            "sha": digest,
            "encoding": "base64",
            "size": len(record),
            "content": base64.b64encode(record).decode(),
        }
    ).encode()


def source_response(kind: str) -> tuple[bytes, str]:
    if kind == "nvd_ollama":
        return (
            ROOT / "fixtures/recorded/nvd_api_20261015_public.json"
        ).read_bytes(), "application/json"
    if kind == "vllm_vendor":
        record = json.loads(
            (ROOT / "fixtures/recorded/vllm_vendor_20261015_public.json").read_bytes()
        )[0]
        return json.dumps([record]).encode(), "application/json"
    if kind == "osv_ollama":
        record = json.loads((REPOSITORY / "osv_ollama_real.body").read_bytes())
        return json.dumps({"vulns": [record]}).encode(), "application/json"
    if kind == "ollama_releases":
        return (REPOSITORY / "ollama_release_real.body").read_bytes(), "application/json"
    if kind == "trailofbits_blog":
        return (FEEDS / "trailofbits_metadata_excerpt.xml").read_bytes(), "application/rss+xml"
    if kind == "arxiv_security":
        return (FEEDS / "doh_06_arxiv_ai_security.body").read_bytes(), "application/atom+xml"
    if kind == "nist_ai_rmf":
        return nist_pdf(), "application/pdf"
    if kind == "cac_generative_ai":
        return (
            ROOT / "fixtures/recorded/cac_generative_ai_20261015_public.html"
        ).read_bytes(), "text/html"
    raise ValueError("fixture source unsupported")
