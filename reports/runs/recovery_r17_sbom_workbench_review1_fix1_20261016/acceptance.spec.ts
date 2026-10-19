import {test,expect} from '../../../frontend/node_modules/@playwright/test/index.mjs';
import {fixture,clearAssertion} from './reviewer_fixture.ts';
import {fixtureAssetId} from '../../../frontend/src/features/assets/synthetic-fixtures.ts';
import {sbomFixture} from '../../../frontend/tests/r17_sbom_fixture.ts';
const originalInputs=[
  'pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env',
  'pkg:pypi/synthetic@review-secret%40private',
  'pkg:generic/synthetic@%252Fhome%252Freview-private',
];
for (const [index,purl] of originalInputs.entries()) for (const target of ['snapshot','reference'] as const) test(`independent acceptance ${index+1} ${target}: original unsafe input clears private DOM`,async({page},info)=>{
  const api=await fixture(page);
  if(target==='snapshot')api.snapshotPurl=purl;else api.referencePurl=purl;
  await page.goto(`/#assets/${fixtureAssetId}`);
  await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible();
  await clearAssertion(page);await expect(page.getByText(purl,{exact:true})).toHaveCount(0);
  if(target==='snapshot')expect(api.paths.some(path=>path.endsWith('/sbom'))).toBe(false);
  expect(api.foreign).toEqual([]);
  await page.screenshot({path:info.outputPath(`acceptance-${index+1}-${target}-cleared.png`),fullPage:true});
});
const scopes=['pkg:npm/@scope/synthetic','pkg:npm/@scope/synthetic@1.2.3','pkg:npm/%40scope/synthetic','pkg:npm/%40scope/synthetic@1.2.3'];
for(const [index,purl] of scopes.entries())test(`independent npm acceptance ${index+1}: legitimate scoped package remains readable`,async({page},info)=>{
  const api=await fixture(page);api.snapshotPurl=purl;api.referencePurl=purl;
  await page.goto(`/#assets/${fixtureAssetId}`);
  await expect(page.getByText(sbomFixture().combined_semantic_sha256,{exact:true})).toBeVisible();
  await expect(page.getByText(purl,{exact:true})).toHaveCount(2);
  await expect(page.getByRole('heading',{name:'快照 #2',exact:true})).toBeVisible();
  await expect(page.getByText(/已清除私有资产工作区/)).toHaveCount(0);
  expect(api.paths.some(path=>path.endsWith('/sbom'))).toBe(true);expect(api.foreign).toEqual([]);
  await page.screenshot({path:info.outputPath(`npm-scope-${index+1}-readable.png`),fullPage:true});
});
