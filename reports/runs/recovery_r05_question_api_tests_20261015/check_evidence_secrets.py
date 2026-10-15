"""Check this test package's evidence for private connection values without printing values."""

import json
import gzip
from pathlib import Path
from urllib.parse import unquote, urlsplit

directory = Path(__file__).resolve().parent
configuration = json.loads(Path("/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json").read_bytes())
secret_url = configuration["TEST_DATABASE_URL"]
password = unquote(urlsplit(secret_url).password or "")
assert secret_url and password
files = [*directory.glob("*.log"), *directory.glob("*.xml"), *directory.glob("*.json")]
files.extend(directory.glob("*.gz"))
report = directory.parents[1] / "tasks/R05-question-api-tests.md"
files.append(report)
violations = []
for path in files:
    content = gzip.decompress(path.read_bytes()).decode("utf-8") if path.suffix == ".gz" else path.read_text(encoding="utf-8")
    if secret_url in content or password in content:
        violations.append(path.name)
print(json.dumps({"files_checked": len(files), "private_connection_violations": violations}))
assert not violations, "private connection values must not appear in task evidence"
