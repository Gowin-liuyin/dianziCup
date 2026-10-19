$ErrorActionPreference='Stop'
$root='D:\dianzi\output\shaowang-paper-figures-20261016'
$map=Get-Content "$root\build\word-mapping.json" -Raw | ConvertFrom-Json
$word=New-Object -ComObject Word.Application
$word.Visible=$false
$word.DisplayAlerts=0
$doc=$word.Documents.Open('D:\dianzi\output\shaowang-report-20261016\deliverables\ShaoWang-技术报告.docx',$false,$true)
try {
 $doc.SaveAs2("$root\build\report-insertion-proof.docx",16)
 foreach($entry in ($map | Sort-Object inline_index -Descending)) {
  $original=$doc.InlineShapes.Item($entry.inline_index)
  $range=$original.Range
  $original.Delete()
  $replacement=$doc.InlineShapes.AddPicture("$root\deliverables\emf\$($entry.id).emf",$false,$true,$range)
  $replacement.LockAspectRatio=-1
  $replacement.Width=$word.CentimetersToPoints(15.5)
 }
 $doc.Repaginate()
 $doc.Save()
 $doc.ExportAsFixedFormat("$root\build\report-insertion-proof.pdf",17)
 $pageMap=@()
 foreach($entry in $map){$pageMap += [pscustomobject]@{id=$entry.id;page=$doc.InlineShapes.Item($entry.inline_index).Range.Information(3)}}
 $pageMap | ConvertTo-Json | Set-Content "$root\build\proof-pages.json" -Encoding utf8
 Write-Output "Replaced $($map.Count) figures with EMF at 15.5 cm; report proof $($doc.ComputeStatistics(2)) pages"
} finally {$doc.Close(0);$word.Quit()}
