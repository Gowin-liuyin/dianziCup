import {readFileSync,writeFileSync} from 'node:fs';
import {strict as assert} from 'node:assert';
import {isSafeSbomPurl,parseSnapshot,AssetResponseScopeMismatch} from '../../../frontend/src/features/assets/asset-contracts';
import {parseSnapshotSbom} from '../../../frontend/src/features/assets/sbom-contracts';
import {sbomFixture,sbomSnapshot} from '../../../frontend/tests/r17_sbom_fixture';
import {fixtureTenant} from '../../../frontend/src/features/assets/synthetic-fixtures';
import {purlProfileCases} from '../../../frontend/tests/r17_purl_profile_cases';
const originalInputs=['pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env','pkg:pypi/synthetic@review-secret%40private','pkg:generic/synthetic@%252Fhome%252Freview-private'];
const receipts=[];
for(const purl of originalInputs){
  assert.equal(isSafeSbomPurl(purl),false);
  const snapshot=sbomSnapshot();snapshot.components[0].purl=purl;
  const sidecar=sbomFixture();sidecar.dependency_edges[0].target_ref=purl;
  assert.throws(()=>parseSnapshot(snapshot,fixtureTenant,snapshot.asset_id),AssetResponseScopeMismatch);
  assert.throws(()=>parseSnapshotSbom(sidecar,fixtureTenant,sbomSnapshot()),AssetResponseScopeMismatch);
  receipts.push({purl,helper:false,snapshot:'AssetResponseScopeMismatch',reference:'AssetResponseScopeMismatch'});
}
const cases=purlProfileCases.map(item=>({...item,frontend:isSafeSbomPurl(item.purl)}));
for(const item of cases)assert.equal(item.frontend,item.expected,item.name);
writeFileSync('../reports/runs/recovery_r17_sbom_workbench_review1_fix1_20261016/frontend_profile_probe.json',JSON.stringify({original:receipts,cases},null,2)+'\n');
console.log(JSON.stringify({original_passed:receipts.length,manual_cases:cases.length,all_manual_match:true}));
