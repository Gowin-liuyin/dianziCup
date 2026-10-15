from pathlib import Path
import datetime,hashlib,json,re,subprocess
report=Path(r'D:\dianzi\reports\reviews\recovery\G-A-R02-persistence-review-1.md')
log=Path(r'D:\dianzi\reports\runs\recovery_r02_persistence_review_1_20261015')
wt=Path(r'C:\Users\yinha\.codex\worktrees\recovery-r02-review\dianzi')
links=re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf-8'))
missing=[link for link in links if not (report.parent/link).resolve().exists()]
assert not missing,missing
p=subprocess.run(['git','status','--porcelain'],cwd=wt,capture_output=True,text=True,check=True)
sha=subprocess.run(['git','rev-parse','HEAD'],cwd=wt,capture_output=True,text=True,check=True).stdout.strip()
assert p.stdout=='' and sha=='0fe642b1c9e5fe4dafa2774e9432bd96079c1b72'
result={'checked_at':datetime.datetime.now().astimezone().isoformat(),'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'relative_links_checked':len(links),'missing_links':missing,'fixed_wt_status':'clean','fixed_wt_sha':sha,'report_verdict':'needs_changes','must_fix_count':4}
(log/'report_final_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
