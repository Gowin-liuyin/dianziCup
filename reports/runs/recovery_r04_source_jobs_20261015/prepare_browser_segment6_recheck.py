"""保留真实浏览器首轮定位失败，用可访问角色复验同一冻结应用。"""

from pathlib import Path

run = Path(__file__).resolve().parent
assert (run / "real_browser_segment6.json").exists()
old = run / "playwright_live.config.mjs"
new = run / "playwright_live_recheck.config.mjs"
assert not new.exists()
new.write_text(old.read_text(encoding="utf-8").replace(
    "real_browser_artifacts", "real_browser_segment6_recheck_artifacts"
).replace(
    '["r04_real_sources.spec.ts", "r17_real_source_workspace.spec.ts"]',
    '"r17_real_source_workspace.spec.ts"',
), encoding="utf-8")
for source, target in (("run_real_browser_segment6.py", "run_real_browser_segment6_recheck.py"),
                       ("run_real_browser_segment6.ps1", "run_real_browser_segment6_recheck.ps1")):
    path = run / target
    assert not path.exists()
    content = (run / source).read_text(encoding="utf-8")
    content = content.replace("real_browser_segment6.json", "real_browser_segment6_recheck.json")
    content = content.replace("real_browser_segment6.log", "real_browser_segment6_recheck.log")
    content = content.replace("run_real_browser_segment6.py", "run_real_browser_segment6_recheck.py")
    content = content.replace("playwright_live.config.mjs", "playwright_live_recheck.config.mjs")
    path.write_text(content, encoding="utf-8")
print("independent artifacts for browser selector recheck prepared")
