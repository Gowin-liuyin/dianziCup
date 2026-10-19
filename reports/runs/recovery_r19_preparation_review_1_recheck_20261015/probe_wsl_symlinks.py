"""Run unchanged scanner/path function AST under native Linux symlink support.

Ubuntu has jsonschema 3.2 without Draft202012Validator, so this is explicitly
function-level validation; it does not claim a Linux CLI rerun.
"""
import ast
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path('/mnt/d/wt/r19-preparation-review-fix1')
RUN=ROOT/'reports/runs/recovery_r19_preparation_review_1_recheck_20261015'
source=ROOT/'scripts/annotation/prepare.py'
names={'PreparationError','object_value','object_list','string_value','list_value','scan_leaks','require_external'}
tree=ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
selected=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names]
namespace={'Path':Path}
exec(compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),str(source),'exec'),namespace)
Error=namespace['PreparationError']
test=Path(tempfile.mkdtemp(prefix='r19-review-explicit-synthetic-symlinks-'))
target=test/'synthetic-public-target'; target.mkdir()
(target/'clean.txt').write_text('Explicit synthetic-only safe file')
linked=test/'root-link'; linked.symlink_to(target,target_is_directory=True)
subroot=test/'nested-public'; subroot.mkdir()
(subroot/'nested-link').symlink_to(target,target_is_directory=True)
repo_link=test/'repo-link'; repo_link.symlink_to(ROOT,target_is_directory=True)
results=[]
cases=[{'case_id':'SYN-SYMLINK-HOLDOUT','event_family_id':'SYN-SYMLINK-FAMILY','split':'holdout',
        'family_aliases':[],'source_refs':[],'evidence':[]}]
for name,call,expected in [
    ('scan_root_symlink',lambda: namespace['scan_leaks'](cases,[linked]),'SCAN_ROOT_MISSING'),
    ('scan_nested_symlink',lambda: namespace['scan_leaks'](cases,[subroot]),'SCAN_SYMLINK_REFUSED'),
    ('external_path_symlink_to_repo',lambda: namespace['require_external'](repo_link/'synthetic-output.json',[ROOT]),'HUMAN_OR_HOLDOUT_PATH_MUST_BE_EXTERNAL'),
]:
    start=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    try:
        call()
        actual='accepted'
    except Error as error:
        actual=str(error)
    results.append({'name':name,'expected':expected,'actual':actual,'passed':actual==expected,
                    'started_at':start,'ended_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')})
output={'function_source':str(source),'selected_original_functions':sorted(names),
        'unmodified_ast':True,'scope':'function-only; Linux CLI unavailable due local jsonschema 3.2',
        'synthetic_fixture_root':str(test),'records':results}
(RUN/'wsl_symlink_probes.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(output,ensure_ascii=False,indent=2))
raise SystemExit(0 if all(record['passed'] for record in results) else 1)
