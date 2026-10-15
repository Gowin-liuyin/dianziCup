"""Make a physical independent copy of previously downloaded locked Linux packages."""

import importlib.metadata
import json
import re
import shutil
import sys
from pathlib import Path

from packaging.requirements import Requirement

run = Path(__file__).resolve().parent
source = Path('/tmp/dianzi-r01-tls-prefix-runtime-20261015/venv')
destination = Path('/tmp/dianzi-r04-api-review-1-20261015/venv')
source_library = source / 'lib/python3.12/site-packages'
target_library = destination / 'lib/python3.12/site-packages'
normalize = lambda name: re.sub(r'[-_.]+', '-', name).lower()
installed = {normalize(dist.metadata['Name']):dist.version for dist in importlib.metadata.distributions(path=[str(source_library)])}
required = {}
for line in (run / 'locked_requirements.txt').read_text().splitlines():
    if not line or line.lstrip().startswith('#'):
        continue
    requirement = Requirement(line)
    if requirement.marker is not None and not requirement.marker.evaluate():
        continue
    expected = str(requirement.specifier).removeprefix('==')
    name = normalize(requirement.name)
    if installed.get(name) != expected:
        raise RuntimeError(f'cached runtime version mismatch for {name}: {installed.get(name)} != {expected}')
    required[name] = expected
for child in source_library.iterdir():
    if child.name.startswith(('__editable__', 'ai_intel_backend')) or child.name in {'ai_intel', '__pycache__'}:
        continue
    target = target_library / child.name
    if child.is_dir():
        shutil.copytree(child, target, dirs_exist_ok=True)
    else:
        shutil.copy2(child, target)
for child in (source / 'bin').iterdir():
    if child.is_symlink() or child.name.startswith(('python', 'activate')):
        continue
    try:
        contents = child.read_text()
    except (UnicodeError, OSError):
        continue
    if contents.startswith('#!'):
        contents = contents.replace(str(source), str(destination))
        target = destination / 'bin' / child.name
        target.write_text(contents)
        target.chmod(child.stat().st_mode & 0o777)
report = {'copy_mode':'physical copy; no shared Windows or Linux site-packages',
    'source_package_runtime':str(source), 'independent_venv':str(destination),
    'python':sys.version,'exact_locked_versions_verified':required, 'package_count':len(required),
    'excluded':'editable ai_intel bindings from the other checkout', 'product_source':'frozen reviewer PYTHONPATH only'}
(run / 'linux_dependency_copy.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
