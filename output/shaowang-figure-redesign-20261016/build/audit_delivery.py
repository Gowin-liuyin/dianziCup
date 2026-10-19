"""Check native figure coverage and export consistency for the delivery."""

import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from PIL import Image
from pypdf import PdfReader

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DELIVERY = ROOT / "deliverables"
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
specs = json.loads(Path("D:/dianzi/output/shaowang-report-20261016/build/figures.json").read_text(encoding="utf-8"))
specs = [item for item in specs if item["id"] != "F-28"]
order = json.loads((BUILD / "slides-order.json").read_text(encoding="utf-8"))
checks = []


def check(name: str, passed: bool) -> None:
    checks.append({"name": name, "passed": passed})


def stable_slide_xml(content: bytes) -> bytes:
    """Ignore generated creation UUIDs while retaining all visible geometry and text."""
    content = re.sub(rb'(<a16:creationId id=")[^"]+("[^>]*>)', rb'\1GENERATED\2', content)
    return re.sub(rb'(<p14:creationId val=")[^"]+("[^>]*>)', rb'\1GENERATED\2', content)


deck = DELIVERY / "ShaoWang-报告配图重绘.pptx"
check("original_figure_order", order == [item["id"] for item in specs])
original_order = json.loads(Path("D:/dianzi/output/shaowang-report-20261016/build/slides-order.json").read_text(encoding="utf-8"))
check("matches_original_report_figure_exports", order == [item for item in original_order if item != "STYLE"])
check("29_unique_figures", len(order) == len(set(order)) == 29)
check("draft_matches_final", deck.read_bytes() == (BUILD / "redrawn-draft.pptx").read_bytes())
with ZipFile(deck) as package:
    slides = sorted((name for name in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)), key=lambda name: int(re.search(r"slide(\d+)", name)[1]))
    notes = [name for name in package.namelist() if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", name)]
    check("slide_and_notes_count", len(slides) == len(notes) == 29)
    native_shapes = native_connectors = native_tables = pictures = 0
    for number, name in enumerate(slides):
        xml = ET.fromstring(package.read(name))
        slide_text = "\n".join(node.text or "" for node in xml.findall(".//a:t", NS))
        check(f"{order[number]}_title_and_id", specs[number]["title"] in slide_text and order[number] in slide_text)
        native_shapes += len(xml.findall(".//p:sp", NS))
        native_connectors += len(xml.findall(".//p:cxnSp", NS))
        native_tables += len(xml.findall(".//a:tbl", NS))
        pictures += len(xml.findall(".//p:pic", NS))
        if order[number] in {"F-03", "F-10", "F-27", "F-30"}:
            check(f"{order[number]}_pending_measurement_visible", "待测" in slide_text)
    check("native_editability", native_shapes > 0 and native_connectors > 0 and native_tables == 2 and pictures == 0)
    with ZipFile(BUILD / "previous-final" / "previous.pptx") as prior:
        changed = [index + 1 for index, name in enumerate(slides) if stable_slide_xml(package.read(name)) != stable_slide_xml(prior.read(name))]
    check("final_refinements_limited_to_reviewed_slides", changed == [1, 4, 24])

for figure_id in order:
    with Image.open(DELIVERY / "fig" / f"{figure_id}.png") as image:
        check(f"{figure_id}_png_2400x1680", image.size == (2400, 1680))
check("pdf_29_pages", len(PdfReader(str(DELIVERY / "ShaoWang-配图预览.pdf")).pages) == 29)
receipt = json.loads((BUILD / "pptx-validation.json").read_text(encoding="utf-8"))
check("package_integrity", receipt["packageIntegrity"]["exitCode"] == 0)
check("layout_geometry", receipt["presentationLayout"]["exitCode"] == 0)
check("first_party_import", receipt["firstPartyImport"]["passed"])
check("final_hash_receipt", receipt["finalSha256"] == hashlib.sha256(deck.read_bytes()).hexdigest())
result = {"status": "passed" if all(item["passed"] for item in checks) else "failed",
          "checks_passed": sum(item["passed"] for item in checks), "checks_total": len(checks),
          "native_shapes": native_shapes, "native_connectors": native_connectors,
          "native_tables": native_tables, "raster_pictures_in_ppt": pictures,
          "final_revision_changed_slides": changed, "checks": checks,
          "sha256": hashlib.sha256(deck.read_bytes()).hexdigest()}
(BUILD / "delivery-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=False))
raise SystemExit(0 if result["status"] == "passed" else 1)
