param()

$ReviewRunDirectory = $PSScriptRoot

function Invoke-ReviewCommand {
    param(
        [string]$Label,
        [string]$Executable,
        [string[]]$CommandArguments,
        [string]$CommandDirectory
    )
    $stdoutPath = Join-Path $ReviewRunDirectory "$Label.stdout.log"
    $stderrPath = Join-Path $ReviewRunDirectory "$Label.stderr.log"
    $startedAt = [DateTimeOffset]::Now.ToString('yyyy-MM-ddTHH:mm:sszzz')
    Push-Location -LiteralPath $CommandDirectory
    try {
        & $Executable @CommandArguments 1> $stdoutPath 2> $stderrPath
        $commandExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    $endedAt = [DateTimeOffset]::Now.ToString('yyyy-MM-ddTHH:mm:sszzz')
    $record = [ordered]@{
        label = $Label
        command_argv = @($Executable) + $CommandArguments
        cwd = $CommandDirectory
        started_at = $startedAt
        ended_at = $endedAt
        exit_code = $commandExitCode
        stdout = [IO.Path]::GetFileName($stdoutPath)
        stderr = [IO.Path]::GetFileName($stderrPath)
        stdout_sha256 = (Get-FileHash -LiteralPath $stdoutPath -Algorithm SHA256).Hash.ToLowerInvariant()
        stderr_sha256 = (Get-FileHash -LiteralPath $stderrPath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $record | ConvertTo-Json -Depth 6 -Compress | Add-Content -LiteralPath (Join-Path $ReviewRunDirectory 'commands.jsonl') -Encoding utf8
    $record | ConvertTo-Json -Depth 6
    Get-Content -LiteralPath $stdoutPath -Raw
    Get-Content -LiteralPath $stderrPath -Raw
}
