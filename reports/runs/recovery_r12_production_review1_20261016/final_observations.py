"""Close independent scope, cleanup, checkout-byte, and test-count observations."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree import ElementTree

from sqlalchemy import create_engine, text

from review_checks import CODE, MATERIAL, ROOT, RUN, owned_url, write_json

for label, args in [
    ('catalog_publication_v3', ['rg', '-n', 'scope_epochs|persist_catalog_documents|outbox|save_change_publication|bump_scope_epoch', 'backend/src/ai_intel/ingestion/catalog_documents.py', 'backend/src/ai_intel/knowledge/revisions.py', 'backend/src/ai_intel/knowledge/persistence.py', 'backend/src/ai_intel/knowledge/event_linking.py']),
    ('source_diff_check', ['git', 'diff', '--check', 'b502b7ea4a2ffdeca24b8edc7fa8a33cc0980457', CODE]),
    ('final_source_status', ['git', 'status', '--short', '--untracked-files=no']),
]:
    started = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    result = subprocess.run(args, cwd=ROOT, capture_output=True)
    (RUN / (label + '.log')).write_bytes(result.stdout + result.stderr)
    write_json(RUN / (label + '.json'), {'argv': args, 'cwd': str(ROOT), 'started_at': started, 'ended_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), 'exit_code': result.returncode})
    assert result.returncode == 0

path = 'reports/tasks/R12-production-hybrid-migration.md'
raw = (ROOT / path).read_bytes()
fixed = subprocess.check_output(['git', 'show', MATERIAL + ':' + path], cwd=ROOT)
assert raw.replace(b'\r\n', b'\n') == fixed
(RUN / 'fixed_material_task_report.md.txt').write_bytes(fixed)
write_json(RUN / 'checkout_byte_observation.json', {'path': path, 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'fixed_blob_sha256': hashlib.sha256(fixed).hexdigest(), 'lf_equal': True, 'raw_crlf_count': raw.count(b'\r\n'), 'action': 'original checkout material untouched; exact immutable Git blob copied into owned run'})

engine = create_engine(owned_url(), hide_parameters=True)
try:
    with engine.connect() as connection:
        db, username, version = connection.execute(text('SELECT current_database(), current_user, version()')).one()
        assert db == 'test_dianzi_r12_prod_review1_20261016' and username.startswith('test_')
        schemas = connection.scalars(text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'test_r12_%'")).all()
        extension = connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        assert not schemas
    write_json(RUN / 'resource_cleanup.json', {'database': db, 'user_is_test_role': True, 'pg_version': version, 'vector_version': extension, 'remaining_own_schemas': schemas, 'opensearch_cleanup': 'every corpus fixture asserted DELETE owned index status 200 or 404; no global index inventory requested'})
finally:
    engine.dispose()

results = {}
for xml in RUN.glob('*.xml'):
    suites = ElementTree.parse(xml).getroot().iter('testsuite')
    results[xml.name] = {key: sum(int(suite.attrib.get(key, '0')) for suite in ElementTree.parse(xml).getroot().iter('testsuite')) for key in ('tests', 'failures', 'errors', 'skipped')}
write_json(RUN / 'independent_test_results.json', results)
print(json.dumps({'cleanup': 'passed', 'test_results': results}))
