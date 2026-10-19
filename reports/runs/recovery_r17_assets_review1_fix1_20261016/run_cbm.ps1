$workspacePath = 'D:\wt\r17-assets-review1-fix1'
$runPath = Join-Path $workspacePath 'reports\runs\recovery_r17_assets_review1_fix1_20261016'
$portablePath = '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp'
$projectName = 'r17_assets_review1_fix1_frontend_full_20261016'
function Invoke-CbmCheck([string]$name, [string[]]$arguments) {
    $startedAt = Get-Date -Format o
    & wsl.exe --exec $portablePath cli --json @arguments *> (Join-Path $runPath "$name.json")
    $checkExit = $LASTEXITCODE
    $receipt = [ordered]@{ command = @('wsl.exe','--exec',$portablePath,'cli','--json') + $arguments; cwd = $workspacePath; started_at = $startedAt; finished_at = (Get-Date -Format o); exit_code = $checkExit; output = "$name.json" }
    [IO.File]::WriteAllText((Join-Path $runPath "$name.command.json"), ($receipt | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    Write-Output "$name exit=$checkExit"
}
Invoke-CbmCheck 'cbm_full_index' @('index_repository','--repo-path','/mnt/d/wt/r17-assets-review1-fix1/frontend/src','--name',$projectName,'--mode','full')
Invoke-CbmCheck 'cbm_full_schema' @('get_graph_schema','--project',$projectName)
Invoke-CbmCheck 'cbm_full_architecture' @('get_architecture','--project',$projectName,'--aspects','all')
Invoke-CbmCheck 'cbm_full_trace' @('trace_path','--project',$projectName,'--function-name','AuthorizedAssets','--direction','both','--depth','3')
