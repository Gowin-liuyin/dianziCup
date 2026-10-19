$ErrorActionPreference = 'Stop'
$syntaxFiles = @('launch_root_pg_packet.ps1', 'launch_root_pg_packet.template.ps1', 'bounded_prepare.ps1', 'bounded_verify.ps1', 'syntax_only.ps1')
foreach ($name in $syntaxFiles) {
    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(($PSScriptRoot + '/' + $name), [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count) { throw ('PowerShell syntax failed: ' + $name) }
}
@{ syntax_only = $true; parsed_files = $syntaxFiles.Count; business_tests_executed = 0 } | ConvertTo-Json -Compress
