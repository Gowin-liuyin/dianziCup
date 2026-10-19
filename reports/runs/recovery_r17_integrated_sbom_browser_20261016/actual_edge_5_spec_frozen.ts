import process from "node:process";
import { createHash } from "node:crypto";
import { execFileSync, spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { cyclonedxInput, spdxInput } from "./helpers/r17-sbom-inputs";

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
  const output = execFileSync("D:/dianzi/backend/.venv/Scripts/python.exe", ["e2e/helpers/r17_sbom_control.py", action, JSON.stringify(payload)], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 10_000 });
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
  expect(control("verify-upload", { snapshot_id: created.snapshot.snapshot_id, raw_sha256: rawSha })).toMatchObject({ raw_sha256: rawSha, snapshot_id: created.snapshot.snapshot_id, migration: "0022_sbom_sidecars", public_schema: "public" });
  return { assetId: created.asset_id, snapshotId: created.snapshot.snapshot_id, rawSha };
}

test.afterEach(async ({ page }, info) => {
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  const logout = page.getByRole("button", { name: "退出登录", exact: true });
  if (await logout.isVisible()) await logout.click();
  writeFileSync(info.outputPath("actual-http-flow.json"), JSON.stringify(httpFlows.get(page), null, 2));
});

test("R17 actual API 01: empty catalog, raw POST, typed sidecar and declaration navigation", async ({ page }, info) => {
  await login(page, 0);
  await expect(page.getByRole("heading", { name: "尚无可见资产清单", exact: true })).toBeVisible();
  await record(page, info, "empty-catalog");
  const created = await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  firstCreated = created;
  await expect(page.getByText("pkg:npm/%40synthetic/root@1.0.0", { exact: true })).toBeVisible();
  await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  await expect(page.locator(".sbom-source-heading").filter({ hasText: "synthetic-root" })).toBeVisible();
  const navigation = page.getByRole("navigation", { name: "当前固定 SBOM 的声明导航" });
  await expect(navigation.getByRole("button")).toHaveCount(6);
  await navigation.getByRole("button", { name: "依赖与标准关系 1", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(`[id='sbom-${created.snapshotId}-relationships']`)).toBeFocused();
  await expect(page.getByRole("table", { name: "SBOM 原始关系声明" }).getByText("dependsOn", { exact: true })).toBeVisible();
  await expect(page.getByText("file:///synthetic-private-location", { exact: true })).toHaveCount(0);
  await expect(page.locator(".sbom-panel").getByText(/redacted-field:/)).toHaveCount(2);
  await expect(page.locator(".sbom-panel").getByText(/redacted-field:/).first()).toBeVisible();
  const delay = spawn("D:/dianzi/backend/.venv/Scripts/python.exe", ["e2e/helpers/r17_sbom_control.py", "sidecar-delay", "{}"], { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  const ended = new Promise<number | null>((resolve) => delay.once("exit", resolve));
  await new Promise<void>((resolve, reject) => { delay.stdout.once("data", () => resolve()); delay.once("error", reject); });
  await page.reload();
  await expect(page.getByText("正在读取固定快照 SBOM 声明…", { exact: true })).toBeVisible();
  await record(page, info, "actual-loading");
  expect(await ended).toBe(0);
  await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  await record(page, info, "cdx-declarations-desktop");
});

test("R17 actual API 02: SPDX relations and public link keep private URI hidden", async ({ page }, info) => {
  await login(page, 1);
  if (firstCreated === null) throw new Error("first synthetic tenant asset required for cross-tenant proof");
  const foreign = await page.request.get(`/v1/assets/${firstCreated.assetId}/snapshots/${firstCreated.snapshotId}/sbom`);
  expect(foreign.status()).toBe(404);
  expect(await foreign.text()).not.toContain(firstCreated.snapshotId);
  await importThroughUi(page, spdxInput(), "spdx_json");
  await expect(page.getByText("DESCRIBES", { exact: true })).toBeVisible();
  await expect(page.getByText("pkg:pypi/synthetic-spdx@2.0", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开服务器提供的公开文档 ↗", exact: true })).toHaveAttribute("href", "https://example.com/synthetic.spdx.json");
  await expect(page.getByText("原 URI 已隐藏 · 不恢复或点击不安全定位", { exact: true })).toBeVisible();
  await expect(page.locator("a[href^='file:']")).toHaveCount(0);
  await expect(page.getByText("file:///synthetic-private-location", { exact: true })).toHaveCount(0);
  await record(page, info, "spdx-privacy");
});

test("R17 actual API 03: three immutable snapshots, unknowns and stale pointer revalidation", async ({ page }, info) => {
  await login(page, 2);
  const first = await importThroughUi(page, cyclonedxInput("1.0.0", false), "cyclonedx_json");
  const me = await page.request.get("/v1/auth/me");
  const identity: unknown = await me.json();
  if (typeof identity !== "object" || identity === null || !("csrf_token" in identity) || typeof identity.csrf_token !== "string") throw new Error("actual CSRF identity missing");
  const conflictingRaw = Buffer.from(cyclonedxInput("2.0.0", true).toString("utf8").replace("root@2.0.0", "root@1.0.0"));
  const rejected = await page.request.post(`/v1/asset-imports?${new URLSearchParams({ asset_id: first.assetId, manifest_format: "cyclonedx_json", display_name: "Synthetic browser · 授权测试清单", source_version: "synthetic-browser-r17", observed_at: "2026-10-16T08:00:00+08:00" })}`, { data: conflictingRaw, headers: { Origin: new URL(page.url()).origin, "Content-Type": "application/json", "X-CSRF-Token": identity.csrf_token, "Idempotency-Key": "synthetic-conflicting-version" } });
  expect(rejected.status()).toBe(422);
  const second = await importThroughUi(page, cyclonedxInput("2.0.0", true), "cyclonedx_json", true);
  const third = await importThroughUi(page, cyclonedxInput(null, false), "cyclonedx_json", true);
  expect(new Set([first.snapshotId, second.snapshotId, third.snapshotId]).size).toBe(3);
  await expect(page.getByRole("heading", { name: "快照 #3", exact: true })).toBeVisible();
  await expect(page.getByText("版本未知", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("未知 · 当前响应未提供", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /查看快照 #1 · 历史/ }).click();
  await expect(page.getByText(first.rawSha, { exact: true })).toBeVisible();
  await expect(page.getByText(/正在查看历史快照/)).toBeVisible();
  await expect(page.getByRole("table", { name: "SBOM 原始关系声明" })).toHaveCount(0);
  await record(page, info, "fixed-history");
  await page.getByRole("button", { name: "查看当前快照", exact: true }).click();
  await page.reload();
  await expect(page.getByText(third.rawSha, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /查看快照 #2 · 历史/ }).click();
  await expect(page.getByText(second.rawSha, { exact: true })).toBeVisible();
  await expect(page.getByText("dependsOn", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "导出证据包 / OpenVEX · 未就绪", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "查询授权外部观察 · 未就绪", exact: true })).toBeDisabled();
});

test("R17 actual API 04: database sidecar outage is partial 503 and recovers on retry", async ({ page }, info) => {
  await login(page, 3);
  const created = await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  control("sidecar-unavailable");
  try {
    const response = page.waitForResponse((value) => new URL(value.url()).pathname.endsWith("/sbom"));
    await page.reload();
    expect((await response).status()).toBe(503);
    await expect(page.getByRole("heading", { name: "快照 #1", exact: true })).toBeVisible();
    await expect(page.getByRole("table", { name: "资产组件声明" })).toBeVisible();
    await expect(page.getByRole("button", { name: "重试固定 SBOM 声明", exact: true })).toBeVisible();
    await expect(page.getByText(created.rawSha, { exact: true })).toHaveCount(0);
    await record(page, info, "actual-503-partial");
  } finally { control("sidecar-restore"); }
  await page.getByRole("button", { name: "重试固定 SBOM 声明", exact: true }).click();
  await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  await record(page, info, "actual-503-recovery");
});

test("R17 actual API 05: real role and session revocation clear private DOM", async ({ page }, info) => {
  await login(page, 4);
  await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  control("revoke-read", { username: actor(4).username });
  const denied = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/assets");
  await page.getByRole("button", { name: "刷新资产与快照", exact: true }).click();
  expect((await denied).status()).toBe(403);
  await expect(page.getByText("当前会话没有此项资产权限，请联系租户管理员。", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前授权资产", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "快照历史", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("选择本地清单", { exact: true })).toHaveCount(0);
  await record(page, info, "actual-403-revocation");
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await login(page, 5);
  await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  control("revoke-session", { username: actor(5).username });
  const expired = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/assets");
  await page.getByRole("button", { name: "刷新资产与快照", exact: true }).click();
  expect((await expired).status()).toBe(401);
  await expect(page.getByText("会话已失效，私有资产已清除", { exact: true })).toBeVisible();
  await expect(page.getByLabel("选择本地清单", { exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  await record(page, info, "actual-401-revocation");
});

test("R17 actual API 06: 390px keyboard, declaration focus and reduced motion", async ({ page }, info) => {
  await login(page, 6);
  await importThroughUi(page, cyclonedxInput("1.0.0", true, 25), "cyclonedx_json");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const target = page.getByRole("navigation", { name: "当前固定 SBOM 的声明导航" }).getByRole("button", { name: "组件来源 25", exact: true });
  await target.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".sbom-declaration-section").first()).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  const components = page.getByRole("table", { name: "资产组件声明" });
  await expect(components.locator("tbody tr")).toHaveCount(20);
  await page.getByRole("button", { name: "下一页组件", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(components.locator("tbody tr")).toHaveCount(5);
  await record(page, info, "actual-mobile-390");
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const transform = await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).transform);
  await record(page, info, "ambient-frame-a");
  await expect.poll(() => page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).transform)).not.toBe(transform);
  await record(page, info, "ambient-frame-b");
});
