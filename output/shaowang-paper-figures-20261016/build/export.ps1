$ErrorActionPreference = 'Stop'
$figureRoot = Split-Path $PSScriptRoot -Parent
$figureOrder = Get-Content (Join-Path $PSScriptRoot 'slides-order.json') -Raw | ConvertFrom-Json
$figurePowerPoint = New-Object -ComObject PowerPoint.Application
$figureDeck = $figurePowerPoint.Presentations.Open((Join-Path $PSScriptRoot 'unlocked.pptx'), $false, $false, $false)
$figureBounds = @()
try {
 for ($index = 1; $index -le $figureDeck.Slides.Count; $index++) {
  $slide = $figureDeck.Slides.Item($index)
  $stem = $figureOrder[$index - 1]
  $left = 900.0; $top = 630.0; $right = 0.0; $bottom = 0.0
  foreach ($s in $slide.Shapes) {
   $left = [Math]::Min($left, $s.Left); $top = [Math]::Min($top, $s.Top)
   $right = [Math]::Max($right, $s.Left + $s.Width); $bottom = [Math]::Max($bottom, $s.Top + $s.Height)
  }
  $grouped = $false
  if ($index -ne 21 -and $index -ne 22) {
   $shapeNames = [object[]](1..$slide.Shapes.Count); $group = $slide.Shapes.Range($shapeNames).Group()
   $group.Name = "$stem - whole figure"
   $group.Export((Join-Path $figureRoot "deliverables\emf\$stem.emf"),5)
   $grouped = $true
  } else {
   $shapeNames = [object[]](1..$slide.Shapes.Count); $slide.Shapes.Range($shapeNames).Export((Join-Path $figureRoot "deliverables\emf\$stem.emf"),5)
  }
  $slide.Export((Join-Path $PSScriptRoot "$stem-full.png"),'PNG',2400,1680)
  $figureBounds += [pscustomobject]@{id=$stem;left=$left;top=$top;right=$right;bottom=$bottom;grouped=$grouped}
 }
 $figureDeck.SaveAs((Join-Path $PSScriptRoot 'grouped.pptx'),24)
 $figureDeck.SaveAs((Join-Path $PSScriptRoot 'full-canvas.pdf'),32)
 $figureBounds | ConvertTo-Json | Set-Content (Join-Path $PSScriptRoot 'bounds.json') -Encoding utf8
 Write-Output "Rendered and exported $($figureDeck.Slides.Count) figures"
} finally { $figureDeck.Saved = $true; $figureDeck.Close(); $figurePowerPoint.Quit() }


