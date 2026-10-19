$ErrorActionPreference = 'Stop'
$reviewRoot = 'D:\wt\r07-core-fix-recheck-v2'
$reviewRun = Join-Path $reviewRoot 'reports\runs\recovery_r07_core_review_1_recheck_v2_20261016'
$reviewProject = 'r07-core-fix-recheck-v2-src-20261016'
$reviewCbm = '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp'
$reviewReceipts = @()
function Invoke-ReviewCommand {
    param([string]$Label, [string]$Executable, [string[]]$Arguments, [string]$Directory)
    $started = Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'
    Push-Location -LiteralPath $Directory
    try {
        $resultText = (& $Executable @Arguments 2>&1 | Out-String)
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    [System.IO.File]::WriteAllText((Join-Path $reviewRun ($Label + '.log')), $resultText, [System.Text.UTF8Encoding]::new($false))
    $script:reviewReceipts += [ordered]@{ label=$Label; argv=@($Executable)+$Arguments; cwd=$Directory; started_at=$started; ended_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'); exit_code=$code; full_sha='cb34097898b412390ee7e119d0d5c2c90d090673'; code_sha='ce1da8811495f1ea1de538c67cb12b16e6d8a280' }
    [System.IO.File]::WriteAllText((Join-Path $reviewRun 'bootstrap_commands.json'), ($script:reviewReceipts | ConvertTo-Json -Depth 10), [System.Text.UTF8Encoding]::new($false))
    Write-Output "$Label exit=$code"
    if ($code -ne 0) { throw "$Label failed exit $code" }
}
$base = @('-d','Ubuntu-22.04','-u','root','--exec','env','XDG_CACHE_HOME=/tmp/dianzi-r07-core-fix-recheck-v2-cache', $reviewCbm,'cli','--json')
Invoke-ReviewCommand 'cbm_index' 'wsl.exe' ($base + @('index_repository','--repo-path','/mnt/d/wt/r07-core-fix-recheck-v2/backend/src','--name',$reviewProject,'--mode','fast')) $reviewRoot
Invoke-ReviewCommand 'cbm_schema' 'wsl.exe' ($base + @('get_graph_schema','--project',$reviewProject)) $reviewRoot
Invoke-ReviewCommand 'cbm_publish_outbound' 'wsl.exe' ($base + @('trace_path','--project',$reviewProject,'--function-name',($reviewProject+'.ai_intel.knowledge.persistence.KnowledgeRepository.publish'),'--direction','outbound','--depth','2','--max-output-tokens','3000')) $reviewRoot
Invoke-ReviewCommand 'cbm_validate_outbound' 'wsl.exe' ($base + @('trace_path','--project',$reviewProject,'--function-name',($reviewProject+'.ai_intel.knowledge.persistence.KnowledgeRepository._validate_submission'),'--direction','outbound','--depth','2','--max-output-tokens','3000')) $reviewRoot
Invoke-ReviewCommand 'cbm_save_outbound' 'wsl.exe' ($base + @('trace_path','--project',$reviewProject,'--function-name',($reviewProject+'.ai_intel.knowledge.persistence.KnowledgeRepository._save_claim'),'--direction','outbound','--depth','2','--max-output-tokens','2500')) $reviewRoot
Invoke-ReviewCommand 'environment_sync' 'C:\Users\yinha\.local\bin\uv.exe' @('sync','--frozen','--offline','--extra','semantic') (Join-Path $reviewRoot 'backend')
