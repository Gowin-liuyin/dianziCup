"""Independently test pinned display helper and real adapter input boundary."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
RUN=Path(__file__).resolve().parent
sys.path.insert(0,str(RUN/"backend_git_probe/backend/src"))
from ai_intel.assets.sbom_inventory import _safe_purl_reference,parse_inventory_input
from ai_intel.domain.access import AccessScope,Role
frontend=json.loads((RUN/"frontend_profile_probe.json").read_text(encoding="utf-8"))
cases=[]
for item in frontend["cases"]:
    actual=_safe_purl_reference(item["purl"])
    cases.append({**item,"backend_profile":actual,"helper_matches":actual==item["frontend"]})
controls=[]
scope=AccessScope.for_authenticated_user("independent-synthetic-fix1","synthetic-assets-tenant",Role.TENANT_ADMIN)
for item in cases:
    if item["helper_matches"]:continue
    payload={"bomFormat":"CycloneDX","specVersion":"1.6","version":1,"components":[{"type":"library","name":"synthetic","purl":item["purl"],"bom-ref":"synthetic-component"}]}
    raw=json.dumps(payload).encode()
    try:
        parse_inventory_input(raw,manifest_format="cyclonedx_json",scope=scope,authorized_asset_tenant_id=scope.tenant_id,asset_id="a0000000-0000-4000-8000-000000000001",snapshot_number=1,source_version="synthetic-fix1",observed_at=datetime.now(timezone.utc),recorded_at=datetime.now(timezone.utc))
        raise AssertionError("control input unexpectedly accepted")
    except ValueError as failure:
        code=getattr(failure,"code",None)
        locator=getattr(failure,"field_locator",None)
        controls.append({"name":item["name"],"input_bytes_sha256":__import__('hashlib').sha256(raw).hexdigest(),"error_type":type(failure).__name__,"code":code,"field_locator":locator,"accepted":False})
        assert code=="invalid_string"
assert sum(item["helper_matches"] for item in cases)==34 and len(controls)==2
result={"backend_git":"5be873ec38a41955b5a58e9762df4b866a7a9d63","cases":cases,"profile_equal":34,"profile_total":36,"adapter_boundary_rejections":controls,"network_calls":0,"pg_calls":0,"http_route_tested":False}
(RUN/"backend_profile_probe.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
print(json.dumps({key:value for key,value in result.items() if key!="cases"}));assert {item['name'] for item in controls}=={'plain tab','plain newline'}
