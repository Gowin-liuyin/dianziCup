$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$figureDir = Join-Path $taskRoot 'fig'
New-Item -ItemType Directory -Path $figureDir -Force | Out-Null
$order = Get-Content (Join-Path $PSScriptRoot 'slides-order.json') -Raw | ConvertFrom-Json
$powerpoint = New-Object -ComObject PowerPoint.Application
$presentation = $powerpoint.Presentations.Open((Join-Path $PSScriptRoot 'figures-draft.pptx'), $true, $false, $false)
try {
    for ($index=1; $index -le $presentation.Slides.Count; $index++) {
        $stem=$order[$index-1]
        $presentation.Slides.Item($index).Export((Join-Path $figureDir "$stem.png"), 'PNG', 2400, 1680)
    }
    $presentation.SaveAs((Join-Path $PSScriptRoot 'figures-all.pdf'), 32)
    Write-Output "Rendered $($presentation.Slides.Count) slides"
} finally {
    $presentation.Close()
    $powerpoint.Quit()
}
