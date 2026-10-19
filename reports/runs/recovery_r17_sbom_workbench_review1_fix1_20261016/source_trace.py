"""Cross-check actual default App and both production PURL caller paths."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
result=subprocess.run(["rg","-n","--glob","!*.test.*","isSafeSbomPurl|parseSnapshot|safeReference|AssetWorkspace|AuthorizedAssets|AssetDetail|SnapshotView|SbomDetail|getAssetSnapshotSbom|parseSnapshotSbom|importAsset|createRoot|API_PROXY_TARGET","frontend/src","frontend/index.html","frontend/vite.config.ts"],cwd=ROOT,capture_output=True)
print(result.stdout.decode("utf-8",errors="replace"));raise SystemExit(result.returncode)
