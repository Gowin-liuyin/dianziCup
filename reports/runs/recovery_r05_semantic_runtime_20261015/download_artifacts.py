"""Selective official artifacts; verified TLS, fixed revisions, bounded bytes and deadline."""
import hashlib
import json
from pathlib import Path
import time
import urllib.request
from datetime import datetime

CACHE = Path(r'C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime')
OUTPUT = Path(__file__).parent
START = time.monotonic()
BUDGET = 3 * 1024**3
MODELS = [('multilingual-e5-small.metadata.json', 'intfloat/multilingual-e5-small', '614241f622f53c4eeff9890bdc4f31cfecc418b3', 'e5'), ('mmarco.metadata.json', 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1', '1427fd652930e4ba29e8149678df786c240d8825', 'mmarco')]
receipt = {'started_at': datetime.now().astimezone().isoformat(), 'artifacts': []}
bytes_downloaded = 0
for metadata_name, model, revision, folder in MODELS:
    metadata = json.loads((CACHE / metadata_name).read_text())
    assert metadata['sha'] == revision
    for filename in ['onnx/model.onnx', 'tokenizer.json', 'config.json']:
        artifact = next(f for f in metadata['files'] if f['rfilename'] == filename)
        expected_size = artifact['size']
        expected_sha = artifact.get('lfs', {}).get('sha256')
        assert bytes_downloaded + expected_size < BUDGET
        destination = CACHE / folder / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        git_digest = hashlib.sha1(b'blob ' + str(expected_size).encode() + b'\x00')
        actual = 0
        url = f'https://huggingface.co/{model}/resolve/{revision}/{filename}'
        with urllib.request.urlopen(url, timeout=30) as response, destination.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                if time.monotonic() - START > 1200:
                    raise TimeoutError('twenty minute download deadline exceeded')
                actual += len(chunk)
                if actual > expected_size:
                    raise ValueError('artifact exceeds fixed metadata size')
                digest.update(chunk)
                git_digest.update(chunk)
                stream.write(chunk)
        assert actual == expected_size
        assert (digest.hexdigest() == expected_sha if expected_sha else git_digest.hexdigest() == artifact['blobId'])
        bytes_downloaded += actual
        entry = {'model': model, 'revision': revision, 'filename': filename, 'source': url, 'bytes': actual, 'sha256': digest.hexdigest(), 'git_blob': artifact['blobId'], 'license': metadata['license']}
        receipt['artifacts'].append(entry)
        (OUTPUT / 'artifacts.json').write_text(json.dumps(receipt, indent=2))
        print(folder, filename, actual, digest.hexdigest(), flush=True)
receipt['ended_at'] = datetime.now().astimezone().isoformat()
receipt['elapsed_seconds'] = time.monotonic() - START
receipt['bytes_downloaded'] = bytes_downloaded
(OUTPUT / 'artifacts.json').write_text(json.dumps(receipt, indent=2))
