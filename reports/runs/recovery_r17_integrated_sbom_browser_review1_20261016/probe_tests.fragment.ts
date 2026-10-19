test("review negative 01: all declaration sections focus and independent source pagination at 390px", async ({ page }, info) => {
  await login(page, 7);
  await importThroughUi(page, cyclonedxInput("1.0.0", true, 25), "cyclonedx_json");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const buttons = page.getByRole("navigation", { name: "当前固定 SBOM 的声明导航" }).getByRole("button");
  for (let index = 0; index < 6; index += 1) {
    const button = buttons.nth(index);
    const sectionId = await button.getAttribute("aria-controls");
    await button.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(`[id='${sectionId}']`)).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  const sources = page.locator(".sbom-declaration-section").filter({ has: page.getByRole("heading", { name: "组件来源", exact: true }) });
  await expect(sources.locator(".sbom-row-list > li")).toHaveCount(20);
  await sources.getByRole("button", { name: "下一页组件来源", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(sources.locator(".sbom-row-list > li")).toHaveCount(5);
  await expect(sources.getByText("synthetic-extra-22", { exact: true })).toBeVisible();
  await sources.getByRole("button", { name: "上一页组件来源", exact: true }).click();
  await expect(sources.locator(".sbom-row-list > li")).toHaveCount(20);
  await record(page, info, "independent-six-sections-390");
});

test("review negative 02: exact UTF8, sidecar-only A-B-A, replay and database immutability", async ({ page }, info) => {
  await login(page, 8);
  const rawA = Buffer.from(cyclonedxInput("1.0.0", false).toString("utf8").replace("synthetic-root", "审查合成-根组件") + "\n  \n", "utf8");
  const rawB = Buffer.from(cyclonedxInput("1.0.0", true).toString("utf8").replace("synthetic-root", "审查合成-根组件") + "\n  \n", "utf8");
  const requestPromise = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/asset-imports" && response.request().method() === "POST");
  const first = await importThroughUi(page, rawA, "cyclonedx_json");
  const originalRequest = (await requestPromise).request();
  const replayKey = await originalRequest.headerValue("idempotency-key");
  if (replayKey === null) throw new Error("original browser idempotency key absent");
  const originalUrl = originalRequest.url();
  const originalFirstSidecar = await page.request.get(`/v1/assets/${first.assetId}/snapshots/${first.snapshotId}/sbom`);
  const frozenSidecar: unknown = await originalFirstSidecar.json();
  const second = await importThroughUi(page, rawB, "cyclonedx_json", true);
  const third = await importThroughUi(page, rawA, "cyclonedx_json", true);
  expect(new Set([first.snapshotId, second.snapshotId, third.snapshotId]).size).toBe(3);
  const identity = await (await page.request.get("/v1/auth/me")).json();
  const replay = await page.request.post(originalUrl, { data: rawA, headers: { Origin: new URL(page.url()).origin, "Content-Type": "application/json", "X-CSRF-Token": identity.csrf_token, "Idempotency-Key": replayKey } });
  expect(replay.status()).toBe(201);
  expect((await replay.json()).snapshot.snapshot_id).toBe(first.snapshotId);
  const current = await page.request.get(`/v1/assets/${first.assetId}`);
  expect((await current.json()).snapshot.snapshot_id).toBe(third.snapshotId);
  const readFirstAgain = await page.request.get(`/v1/assets/${first.assetId}/snapshots/${first.snapshotId}/sbom`);
  expect(await readFirstAgain.json()).toEqual(frozenSidecar);
  const rawHashes = [rawA, rawB, rawA].map((raw) => createHash("sha256").update(raw).digest("hex"));
  const audited = JSON.parse(execFileSync("D:/dianzi/backend/.venv/Scripts/python.exe", ["../reports/runs/recovery_r17_integrated_sbom_browser_review1_20261016/independent_control.py", JSON.stringify({ asset_id: first.assetId, raw_hashes: rawHashes })], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 10_000 }));
  expect(audited.mutation_rejections).toHaveLength(4);
  expect(audited.current_snapshot_id).toBe(third.snapshotId);
  writeFileSync(info.outputPath("independent-immutable-replay.json"), JSON.stringify({ audited, replay_status: replay.status(), old_fixed_sidecar_equal: true }, null, 2));
  await page.getByRole("button", { name: /查看快照 #1 · 历史/ }).click();
  await expect(page.getByText(first.rawSha, { exact: true })).toBeVisible();
  await expect(page.locator(".sbom-source-heading").getByText("审查合成-根组件", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "SBOM 原始关系声明" })).toHaveCount(0);
  await record(page, info, "independent-history-after-replay");
});

test("review negative 03: foreign detail, current, history, fixed snapshot and sidecar return empty privacy boundary", async ({ page }, info) => {
  await login(page, 9);
  const created = await importThroughUi(page, spdxInput(), "spdx_json");
  const visiblePrivate = "Synthetic browser · 授权测试清单";
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await login(page, 10);
  const checks = [];
  for (const suffix of ["", "/snapshots", `/snapshots/${created.snapshotId}`, `/snapshots/${created.snapshotId}/sbom`]) {
    const response = await page.request.get(`/v1/assets/${created.assetId}${suffix}`);
    expect(response.status()).toBe(404);
    const body = await response.json();
    expect(body).not.toHaveProperty("tenant_id");
    expect(body).not.toHaveProperty("snapshot");
    expect(body).not.toHaveProperty("components");
    expect(JSON.stringify(body)).not.toContain(visiblePrivate);
    checks.push({ suffix, status: response.status(), body });
  }
  await page.goto(`/#assets/${created.assetId}`);
  await expect(page.getByText(visiblePrivate, { exact: true })).toHaveCount(0);
  await expect(page.getByText(created.rawSha, { exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "快照历史", exact: true })).toHaveCount(0);
  writeFileSync(info.outputPath("independent-foreign-endpoints.json"), JSON.stringify(checks, null, 2));
  await record(page, info, "independent-foreign-details");
});
