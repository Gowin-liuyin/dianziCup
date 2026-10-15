$ErrorActionPreference = 'Stop'
$modules = 'C:/Users/yinha/.codex/worktrees/r04-ui-time-review/dianzi/frontend/node_modules'
if (-not (Test-Path -LiteralPath $modules)) { New-Item -ItemType Junction -Path $modules -Target 'C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi/frontend/node_modules' | Out-Null }
$identity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
try {
 $env:DIANZI_E2E_USERNAME = $identity.DIANZI_E2E_USERNAME
 $env:DIANZI_E2E_PASSWORD = $identity.DIANZI_E2E_PASSWORD
 & 'D:/dianzi/backend/.venv/Scripts/python.exe' "$PSScriptRoot/time_recheck.py"
 exit $LASTEXITCODE
} finally {Remove-Item Env:DIANZI_E2E_USERNAME -ErrorAction SilentlyContinue;Remove-Item Env:DIANZI_E2E_PASSWORD -ErrorAction SilentlyContinue;$identity=$null}
