import { test, expect } from "../../../frontend/node_modules/@playwright/test/index.mjs";
import { fixture, clearAssertion } from "./reviewer_fixture";
import { fixtureAssetId } from "../../../frontend/src/features/assets/synthetic-fixtures";

const originalInputs = [
  "pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env",
  "pkg:pypi/synthetic@review-secret%40private",
  "pkg:generic/synthetic@%252Fhome%252Freview-private",
];
for (const target of ["snapshot", "reference"] as const) for (const [index, purl] of originalInputs.entries()) {
  test("Must1 acceptance " + target + " " + (index + 1) + ": unsafe version never enters private DOM", async ({ page }, info) => {
    const api = await fixture(page);
    if (target === "snapshot") api.snapshotPurl = purl; else api.referencePurl = purl;
    await page.goto("/#assets/" + fixtureAssetId);
    await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible();
    await clearAssertion(page);
    await expect(page.getByText(purl, { exact: true })).toHaveCount(0);
    if (target === "snapshot") expect(api.paths.some((path) => path.endsWith("/sbom"))).toBe(false);
    expect(api.foreign).toEqual([]);
    await page.screenshot({ path: info.outputPath("must1-" + target + "-" + (index + 1) + "-revoked.png") });
  });
}
for (const purl of ["pkg:npm/@scope/synthetic", "pkg:npm/@scope/synthetic@1.2.3", "pkg:npm/%40scope/synthetic", "pkg:npm/%40scope/synthetic@1.2.3"]) {
  test("npm scope acceptance " + purl + ": legitimate package is displayed", async ({ page }) => {
    const api = await fixture(page); api.snapshotPurl = purl; api.referencePurl = purl;
    await page.goto("/#assets/" + fixtureAssetId);
    await expect(page.getByRole("heading", { name: "快照 #2", exact: true })).toBeVisible();
    await expect(page.getByText(purl, { exact: true })).toHaveCount(2);
    await expect(page.getByText(/已清除私有资产工作区/)).toHaveCount(0);
    expect(api.foreign).toEqual([]);
  });
}
