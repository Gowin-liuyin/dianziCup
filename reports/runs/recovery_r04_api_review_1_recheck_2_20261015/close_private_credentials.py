"""Remove only the already scanned review-owned root0600 credential files."""

import json
from pathlib import Path

directories = ['dianzi-r04-api-review-1-20261015','dianzi-r04-api-review-1-recheck-20261015','dianzi-r04-api-review-1-recheck-2-20261015']
rows = []
for name in directories:
    expected_directory = Path('/tmp')/name
    assert expected_directory.resolve() == expected_directory
    removed = []
    for filename in ['connection.json','review_registered_secrets.json']:
        path = expected_directory/filename
        assert path.resolve() == path
        if path.exists():
            assert path.stat().st_mode & 0o777 == 0o600
            path.unlink()
            removed.append(filename)
    rows.append({'review_private_directory':str(expected_directory),'removed_credential_files':removed,
        'credential_files_remaining':sum((expected_directory/name).exists() for name in ['connection.json','review_registered_secrets.json'])})
result = {'review_only':True,'recursive_delete_used':False,'shared_test_or_product_credentials_modified':False,'rows':rows}
run = Path(__file__).resolve().parent
(run/'private_credentials_release.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
