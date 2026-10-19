$ErrorActionPreference = 'Stop'
$figureRoot = Split-Path $PSScriptRoot -Parent
$figureDirectory = Join-Path $figureRoot 'deliverables\fig'
$figureOrder = Get-Content (Join-Path $PSScriptRoot 'slides-order.json') -Raw | ConvertFrom-Json
$figurePowerPoint = New-Object -ComObject PowerPoint.Application
$figureDeck = $figurePowerPoint.Presentations.Open((Join-Path $PSScriptRoot 'redrawn-draft.pptx'), $true, $false, $false)
try {
    for ($index = 1; $index -le $figureDeck.Slides.Count; $index++) {
        $stem = $figureOrder[$index - 1]
        $figureDeck.Slides.Item($index).Export((Join-Path $figureDirectory "$stem.png"), 'PNG', 2400, 1680)
    }
    $figureDeck.SaveAs((Join-Path $PSScriptRoot 'figures-review.pdf'), 32)
    Write-Output "Rendered $($figureDeck.Slides.Count) slides"
} finally {
    $figureDeck.Close()
    $figurePowerPoint.Quit()
}
