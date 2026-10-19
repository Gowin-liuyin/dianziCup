$ErrorActionPreference='Stop'
$p=New-Object -ComObject PowerPoint.Application
$d=$p.Presentations.Open('D:\dianzi\output\shaowang-paper-figures-20261016\build\redrawn-draft.pptx',$false,$false,$false)
try {
 $slide=$d.Slides.Item(1)
 $indices = [object[]](1..$slide.Shapes.Count)
 $r=$slide.Shapes.Range($indices)
 Write-Output "Shape count $($slide.Shapes.Count) range $($r.Count)"
 $g=$r.Group()
 Write-Output "Group $($g.GroupItems.Count)"
} finally { $d.Saved=$true; $d.Close();$p.Quit() }
