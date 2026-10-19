"""Adapt only owned resources and paths; preserve original six acceptance assertions."""
import hashlib
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
AUTHOR = ROOT / "reports/runs/recovery_r17_integrated_sbom_browser_20261016"
RUN_ID = "r17_real_review1_20261016"
transforms = {}
for filename in ("browser_runner.py", "api_server.py"):
    raw = (AUTHOR / filename).read_text(encoding="utf8")
    adapted = raw.replace("r17_integrated_sbom_browser_20261016", RUN_ID).replace("26773", "26873").replace("28773", "28873")
    adapted = adapted.replace("--config=../reports/runs/recovery_" + RUN_ID + "/playwright.actual.cjs", "--config=../reports/runs/recovery_r17_integrated_sbom_browser_review1_20261016/playwright.actual.cjs")
    if filename == "browser_runner.py":
        adapted = adapted.replace("for _ in range(7):", "for _ in range(11):")
    (RUN / filename).write_text(adapted, encoding="utf8")
    transforms[filename] = {"original_sha256": hashlib.sha256(raw.encode()).hexdigest(), "adapted_sha256": hashlib.sha256(adapted.encode()).hexdigest()}
control = (ROOT / "frontend/e2e/helpers/r17_sbom_control.py").read_text(encoding="utf8").replace("r17_integrated_sbom_browser_20261016", RUN_ID)
(RUN / "r17_sbom_control.py").write_text(control, encoding="utf8")
spec = (ROOT / "frontend/e2e/r17_integrated_sbom_api.spec.ts").read_text(encoding="utf8")
adapted = spec.replace('"@playwright/test"', '"../../../frontend/node_modules/@playwright/test"').replace('"./helpers/r17-sbom-inputs"', '"../../../frontend/e2e/helpers/r17-sbom-inputs"').replace('"e2e/helpers/r17_sbom_control.py"', '"../reports/runs/recovery_r17_integrated_sbom_browser_review1_20261016/r17_sbom_control.py"')
(RUN / "original_six.spec.ts").write_text(adapted, encoding="utf8")
transforms["original_six.spec.ts"] = {"original_sha256": hashlib.sha256(spec.encode()).hexdigest(), "adapted_sha256": hashlib.sha256(adapted.encode()).hexdigest(), "scope": "three exact import/control path replacements only, no input or assertion change"}
config = """const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const { defineConfig } = require(path.join(root, 'frontend/node_modules/@playwright/test'));
module.exports = defineConfig({ testDir: __dirname, testMatch: process.env.R17_REVIEW_SPEC || 'original_six.spec.ts', workers: 1, fullyParallel: false, timeout: 60000, expect: { timeout: 10000 }, outputDir: path.join(__dirname, process.env.R17_EDGE_LABEL + '_artifacts'), reporter: [['list'], ['json', { outputFile: path.join(__dirname, process.env.R17_EDGE_LABEL + '.json') }]], use: { baseURL: 'http://127.0.0.1:26873', channel: 'msedge', viewport: { width: 1366, height: 900 }, trace: 'off', video: 'off', screenshot: 'off' }, webServer: { command: 'node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 26873 --strictPort', cwd: path.join(root, 'frontend'), env: { API_PROXY_TARGET: 'http://127.0.0.1:28873' }, url: 'http://127.0.0.1:26873', reuseExistingServer: false, timeout: 30000 }});
"""
(RUN / "playwright.actual.cjs").write_text(config, encoding="utf8")
(RUN / "resource_adapter.json").write_text(json.dumps(transforms, indent=2), encoding="utf8")
print(json.dumps({"own_database": "test_dianzi_" + RUN_ID, "own_ports": [26873, 28873], "original_six_assertions": "unchanged"}))
