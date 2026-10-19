$ErrorActionPreference = 'Stop'
$taskRoot = 'D:\dianzi\output\shaowang-report-20261016'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $document = $word.Documents.Open("$taskRoot\deliverables\ShaoWang-技术报告.docx", $false, $false)
    $document.Fields.Update() | Out-Null
    foreach ($toc in $document.TablesOfContents) { $toc.Update() }
    foreach ($toc in $document.TablesOfContents) {
        $toc.Range.Font.Size = 11
        $toc.Range.ParagraphFormat.LineSpacingRule = 0
        $toc.Range.ParagraphFormat.SpaceBefore = 0
        $toc.Range.ParagraphFormat.SpaceAfter = 0
    }
    $document.Repaginate()
    $document.Fields.Update() | Out-Null
    foreach ($toc in $document.TablesOfContents) { $toc.Update() }
    foreach ($toc in $document.TablesOfContents) {
        $toc.Range.Font.Size = 11
        $toc.Range.ParagraphFormat.LineSpacingRule = 0
        $toc.Range.ParagraphFormat.SpaceBefore = 0
        $toc.Range.ParagraphFormat.SpaceAfter = 0
    }
    $document.Repaginate()
    foreach ($toc in $document.TablesOfContents) { $toc.UpdatePageNumbers() }
    $document.Save()
    $document.ExportAsFixedFormat("$taskRoot\build\report.pdf", 17)
    $pages = $document.ComputeStatistics(2)
    $paragraphs = @()
    foreach ($paragraph in $document.Paragraphs) {
        if ($paragraph.OutlineLevel -le 3) {
            $paragraphs += [PSCustomObject]@{text=$paragraph.Range.Text.Trim(); page=$paragraph.Range.Information(3)}
        }
    }
    $paragraphs | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$taskRoot\build\word-pages.json" -Encoding utf8
    Write-Output "Word updated fields and exported PDF: $pages pages"
    $document.Close(0)
} finally {
    $word.Quit()
}
