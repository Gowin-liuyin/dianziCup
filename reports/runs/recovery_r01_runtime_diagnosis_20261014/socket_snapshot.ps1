$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$runtimePath = Join-Path $env:LOCALAPPDATA 'Docker\run\dockerInference'
$runtimeDirectory = Get-Item -LiteralPath (Split-Path -Parent $runtimePath) -Force | Select-Object FullName,Attributes,LinkType,Target,CreationTime,LastWriteTime
try {
    $runtimeFile = Get-Item -LiteralPath $runtimePath -Force | Select-Object FullName,Length,Attributes,LinkType,Target,CreationTime,LastWriteTime
    $runtimeError = $null
} catch {
    $runtimeFile = $null
    $runtimeError = $_.Exception.Message
}
$dockerStorage = Get-ChildItem -LiteralPath (Join-Path $env:LOCALAPPDATA 'Docker\wsl') -Filter '*.vhdx' -File -Recurse -ErrorAction SilentlyContinue | Select-Object FullName,Length,Attributes,LastWriteTime
[ordered]@{ recorded_at = [DateTimeOffset]::Now.ToString('o'); runtime_directory = $runtimeDirectory; inference_listener_file = $runtimeFile; inference_listener_metadata_error = $runtimeError; docker_virtual_disks = @($dockerStorage) } | ConvertTo-Json -Depth 4
