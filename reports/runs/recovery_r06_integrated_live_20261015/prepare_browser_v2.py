"""Keep the initial failed instrument immutable and correct selectors/filter state in a new copy."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
original = RUN / "integrated-live.spec.cjs"
config = RUN / "playwright.config.cjs"
target = RUN / "integrated-live.v2.spec.cjs"
assert not target.exists()
content = original.read_text(encoding="utf-8")
content = content.replace('page.getByLabel("固定来源", { exact: true })', 'page.locator("#source-kind")')
content = content.replace('page.getByLabel("采集流", { exact: true })', 'page.locator("#source-stream")')
content = content.replace('await page.getByLabel("检索关键词", { exact: true }).fill(saved.title);', 'await page.getByLabel("来源类别", { exact: true }).selectOption("");\n    await page.getByLabel("检索关键词", { exact: true }).fill(saved.title);')
content = content.replace('"source-admin-visible-1366.png"', '"source-admin-visible-v2-1366.png"')
content = content.replace('"browser_manual_collection.json"', '"browser_manual_collection_v2.json"')
content = content.replace('`document-visible-${width}.png`', '`document-visible-v2-${width}.png`')
target.write_text(content, encoding="utf-8")
new_config = config.read_text().replace('"integrated-live.spec.cjs"', '"integrated-live.v2.spec.cjs"').replace('"browser_artifacts"', '"browser_artifacts_v2"').replace('"browser_report.json"', '"browser_report_v2.json"')
(RUN / "playwright.v2.config.cjs").write_text(new_config, encoding="utf-8")
(RUN / "browser_instrument_v2.json").write_text(json.dumps({"prepared_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": "1156b2ed6616e3a4297215c2893d2cbe633f5215", "original_spec_sha256": hashlib.sha256(original.read_bytes()).hexdigest(), "original_config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(), "new_spec_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "corrections": ["nested source label includes option text; use frozen source-kind/source-stream IDs", "clear retained category filter before NIST title search"], "product_changed": False, "original_red_files_overwritten": False}, indent=2) + "\n", encoding="utf-8")
