"""Compare all review/authored data bytes with actual in-memory test and environment secrets."""

import gzip
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
REPORT = ROOT / 'reports/reviews/recovery/G-C-R07-default-durable-entry-review-1-recheck.md'
script = '$resourceEncoded = Get-Content -LiteralPath D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi -Raw; $resourceSecure = ConvertTo-SecureString $resourceEncoded; [Console]::Write((ConvertFrom-SecureString -SecureString $resourceSecure -AsPlainText))'
private = subprocess.run(['C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe', '-NoProfile', '-Command', script], capture_output=True, check=True, timeout=20)
reference = json.loads(private.stdout)
url = make_url(reference['TEST_DATABASE_URL'])
values = {reference['TEST_DATABASE_URL'], url.password, reference.get('postgres_password'), reference.get('redis_password')}
for run_id in ('r07_execution_api_review1_fix1_20261016', 'r07_execution_scope_review1_fix1_20261016'):
    values.add(url.set(database='test_dianzi_' + run_id).render_as_string(hide_password=False))
for name, value in os.environ.items():
    if re.search(r'(API_KEY|SECRET|PASSWORD|TOKEN)$', name) and len(value) >= 8:
        values.add(value)
values = {value.encode('utf-8') for value in values if value}
paths = {path for path in RUN.rglob('*') if path.is_file() and '__pycache__' not in path.parts}
if REPORT.exists():
    paths.add(REPORT)
fixed = json.loads((ROOT / 'reports/runs/recovery_r07_idempotency_scope_20261016/bytes_fix_manifest.json').read_bytes())
for group in ('original_material_rows_git_verified', 'additional_material_rows_git_verified', 'source_rows_frozen_code_verified'):
    paths.update(ROOT / row['path'] for row in fixed[group])
paths.add(ROOT / 'reports/runs/recovery_r07_idempotency_scope_20261016/bytes_fix_manifest.json')
hits, compressed = [], []
for path in sorted(paths):
    assert '__pycache__' not in path.parts
    raw = path.read_bytes()
    payloads = [raw]
    if path.suffix == '.gz':
        payloads.append(gzip.decompress(raw))
        compressed.append(path.relative_to(ROOT).as_posix())
    elif path.suffix == '.zst':
        linux_path = '/mnt/d/' + str(path).replace('\\', '/').split(':/', 1)[1]
        decoder = "import ctypes,pathlib,sys; x=pathlib.Path(sys.argv[1]).read_bytes(); z=ctypes.CDLL('libzstd.so.1'); z.ZSTD_getFrameContentSize.argtypes=[ctypes.c_void_p,ctypes.c_size_t]; z.ZSTD_getFrameContentSize.restype=ctypes.c_ulonglong; z.ZSTD_decompress.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t]; z.ZSTD_decompress.restype=ctypes.c_size_t; z.ZSTD_isError.argtypes=[ctypes.c_size_t]; z.ZSTD_isError.restype=ctypes.c_uint; n=z.ZSTD_getFrameContentSize(x,len(x)); n=67108864 if n in [18446744073709551615,18446744073709551614] else n; assert 0<n<=67108864; out=ctypes.create_string_buffer(n); got=z.ZSTD_decompress(out,n,x,len(x)); assert not z.ZSTD_isError(got); sys.stdout.buffer.write(out.raw[:got])"
        decoded = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', '/usr/bin/python3', '-c', decoder, linux_path], capture_output=True, check=True, timeout=30)
        payloads.append(decoded.stdout)
        compressed.append(path.relative_to(ROOT).as_posix())
    if any(value in payload for value in values for payload in payloads):
        hits.append(path.relative_to(ROOT).as_posix())
result = {'created_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'scope': 'owned raw/report and final authored 48+10 material rows/7 source rows; generated pyc excluded without reading', 'files_scanned': len(paths), 'compressed_payloads_decoded': compressed, 'actual_sensitive_value_matches': len(hits), 'matched_paths': hits, 'private_values_or_their_hashes_written': False, 'value_source': 'protected local runtime reference and controlled environment read only in memory'}
if '--read-only' not in sys.argv:
    (RUN / 'actual_value_scan.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'files_scanned': len(paths), 'compressed_payload_count': len(compressed), 'actual_sensitive_value_matches': len(hits)}))
assert not hits, 'actual sensitive value remains; values are never printed'
