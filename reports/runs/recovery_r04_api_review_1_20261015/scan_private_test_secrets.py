"""Inspect only reviewer-owned evidence with test-only secrets held in root0600 storage."""

import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

run = Path(__file__).resolve().parent
private = Path('/tmp/dianzi-r04-api-review-1-20261015')
connection = json.loads((private/'connection.json').read_text())
dsn = connection['TEST_DATABASE_URL']
password = unquote(urlsplit(dsn).password or '')
registered = json.loads((private/'review_registered_secrets.json').read_text()) if (private/'review_registered_secrets.json').exists() else []
full_values = {dsn, password, *registered}
fragments = {value[index:index+8] for value in {password, *registered} if value for index in range(max(0,len(value)-7))}
paths = [path for path in run.rglob('*') if path.is_file() and path.suffix in {'.py','.log','.json','.xml','.txt','.md'}]
report = Path('/mnt/d/dianzi/reports/reviews/recovery/G-B-R04-api-review-1.md')
paths.append(report)
hits = []
for path in paths:
    contents = path.read_bytes()
    kinds = []
    if any(value.encode() in contents for value in full_values if value):
        kinds.append('full_value')
    if any(fragment.encode() in contents for fragment in fragments):
        kinds.append('8_character_fragment')
    if kinds:
        hits.append({'path':str(path),'match_kinds':kinds})
result = {'connection_file_mode':oct((private/'connection.json').stat().st_mode & 0o777),
    'registered_dynamic_credential_count':len(registered),'full_value_count':len(full_values),
    'fragment_count':len(fragments),'scanned_file_count':len(paths),'hits':hits,
    'dsn_or_secret_values_printed':False, 'scope':'reviewer-owned report/run evidence only; no product .env/keys/holdout read'}
(run/'private_test_secret_scan.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
raise SystemExit(1 if hits else 0)
