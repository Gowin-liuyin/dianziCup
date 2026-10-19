$p=New-Object -ComObject PowerPoint.Application
$d=$p.Presentations.Open('D:\dianzi\output\shaowang-paper-figures-20261016\build\redrawn-draft.pptx',$true,$false,$false)
$d.Slides.Item(1).Shapes | Select-Object Id,Name,Type,HasTextFrame,Left,Top,Width,Height | ConvertTo-Json -Depth 2
$d.Close()
$p.Quit()
