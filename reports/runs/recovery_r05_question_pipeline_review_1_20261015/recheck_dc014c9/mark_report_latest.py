from pathlib import Path
report = Path('D:/dianzi/reports/reviews/recovery/G-B-R05-question-pipeline-review-1.md')
content = report.read_text(encoding='utf-8-sig')
headline = '> 最新限定结论（2026-10-15T17:36:29+08:00）：dc014 修复冻结已定向复核，三 Must 在新预约/事务提交范围关闭，限定 Ship；整 R05/G-B/live 未签。原 d7 初审与全部红例保留，详见文末复核节。\n\n'
content = content.replace('# G-B / R05 问答接线独立初审 1\n\n', '# G-B / R05 问答接线独立初审 1\n\n' + headline, 1)
report.write_text(content, encoding='utf-8')
print('report written: ' + str(report))
