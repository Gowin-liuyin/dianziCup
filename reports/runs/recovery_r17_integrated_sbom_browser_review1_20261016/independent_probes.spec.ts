import process from "node:process";
import { createHash } from "node:crypto";
import { execFileSync, spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
import { expect, test, type Page, type TestInfo } from "../../../frontend/node_modules/@playwright/test";
import { cyclonedxInput, spdxInput } from "../../../frontend/e2e/helpers/r17-sbom-inputs";

const httpFlows = new WeakMap<Page, { path: string; method: string; status: number; observed_at: string }[]>();
let firstCreated: { assetId: string; snapshotId: string } | null = null;
test.beforeEach(async ({ page }) => {
  const responses: { path: string; method: string; status: number; observed_at: string }[] = [];
  httpFlows.set(page, responses);
  page.on("response", (response) => {
    const path = new URL(response.url()).pathname;
    if (path.startsWith("/v1/")) responses.push({ path, method: response.request().method(), status: response.status(), observed_at: new Date().toISOString() });
  });
});

function actor(index: number): { username: string; password: string } {
  const accounts: unknown = JSON.parse(process.env.R17_BROWSER_ACCOUNTS ?? "null");
  if (!Array.isArray(accounts)) throw new Error("isolated browser actors must be injected");
  const account: unknown = accounts[index];
  if (typeof account !== "object" || account === null || !("username" in account) || !("password" in account) || typeof account.username !== "string" || typeof account.password !== "string") throw new Error("isolated actor schema invalid");
  return { username: account.username, password: account.password };
}

function control(action: string, payload: Record<string, string> = {}): unknown {
  const output = execFileSync("D:/dianzi/backend/.venv/Scripts/python.exe", ["../reports/runs/recovery_r17_integrated_sbom_browser_review1_20261016/r17_sbom_control.py", action, JSON.stringify(payload)], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 10_000 });
  return JSON.parse(output);
}

async function login(page: Page, index: number) {
  const account = actor(index);
  await page.goto("/#session");
  await page.getByLabel("用户名", { exact: true }).fill(account.username);
  await page.getByLabel("密码", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "资产自查", exact: true }).click();
  await expect(page.getByText("合成 Fixture · 非真实资产", { exact: true })).toBeVisible();
  const session = (await page.context().cookies()).find((cookie) => cookie.name === "ai_intel_session");
  expect(session?.httpOnly).toBe(true);
  expect(session?.sameSite).toBe("Strict");
}

async function record(page: Page, info: TestInfo, name: string) {
  const screenshot = info.outputPath(name + ".png");
  await page.screenshot({ path: screenshot, fullPage: true });
  await page.screenshot({ path: info.outputPath(name + "-viewport.png") });
  writeFileSync(info.outputPath(name + ".json"), JSON.stringify({ name, observed_at: new Date().toISOString(), url: page.url(), viewport: page.viewportSize(), screenshot, data_mode: "fixture", actual_api: true }, null, 2));
}

async function importThroughUi(page: Page, raw: Buffer, format: "cyclonedx_json" | "spdx_json", append = false) {
  if ((await page.locator(".asset-import-panel").getAttribute("open")) === null) await page.locator(".asset-import-panel summary").click();
  await page.getByLabel("清单格式", { exact: true }).selectOption(format);
  await page.getByLabel("选择本地清单", { exact: true }).setInputFiles({ name: "synthetic-browser.json", mimeType: "application/json", buffer: raw });
  if (append) await page.getByLabel("追加到当前所选资产（名称保持一致）", { exact: true }).check();
  else await page.getByLabel("资产名称", { exact: true }).fill("Synthetic browser · 授权测试清单");
  await page.getByLabel("输入来源版本", { exact: true }).fill("synthetic-browser-r17");
  await page.getByLabel("实际观察时间（含时区）", { exact: true }).fill("2026-10-16T08:00:00+08:00");
  const responsePromise = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/asset-imports" && response.request().method() === "POST");
  await page.getByRole("button", { name: "提交授权清单", exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(201);
  const capturedBody = response.request().postDataBuffer();
  if (capturedBody !== null) expect(capturedBody).toEqual(raw);
  const created: unknown = await response.json();
  if (typeof created !== "object" || created === null || !("asset_id" in created) || typeof created.asset_id !== "string" || !("snapshot" in created) || typeof created.snapshot !== "object" || created.snapshot === null || !("snapshot_id" in created.snapshot) || typeof created.snapshot.snapshot_id !== "string") throw new Error("actual import response invalid");
  await expect(page.getByRole("heading", { name: "Synthetic browser · 授权测试清单", exact: true })).toBeVisible();
  await expect(page.getByText("r11-sbom-adapter-1", { exact: true })).toBeVisible();
  const rawSha = createHash("sha256").update(raw).digest("hex");
  const verified = control("verify-upload", { snapshot_id: created.snapshot.snapshot_id, raw_sha256: rawSha });
  expect(verified).toMatchObject({ raw_sha256: rawSha, snapshot_id: created.snapshot.snapshot_id, migration: "0022_sbom_sidecars", public_schema: "public" });
  await expect(page.getByText(rawSha, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "刷新资产与快照", exact: true })).toBeEnabled();
  writeFileSync(test.info().outputPath(`pg-upload-${created.snapshot.snapshot_id}.json`), JSON.stringify({ verified, expected_raw_sha256: rawSha, manifest_format: format, wire_body_available: capturedBody !== null }, null, 2));
  writeFileSync(test.info().outputPath(`synthetic-upload-${created.snapshot.snapshot_id}.json`), raw);
  return { assetId: created.asset_id, snapshotId: created.snapshot.snapshot_id, rawSha };
}

test.afterEach(async ({ page }, info) => {
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  const logout = page.getByRole("button", { name: "退出登录", exact: true });
  if (await logout.isVisible()) await logout.click();
  writeFileSync(info.outputPath("actual-http-flow.json"), JSON.stringify(httpFlows.get(page), null, 2));
});

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
