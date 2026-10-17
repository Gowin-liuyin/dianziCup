import { writeFile } from "node:fs/promises";
import process from "node:process";
import { expect, test, type Page, type TestInfo } from "@playwright/test";

export function isPrivateWorkspaceUrl(url: string): boolean {
  return /^\/(?:api\/)?v1\/(?:events|evidence|documents|questions|answers|sources|jobs|assets|asset-imports|assessments|investigations|subscriptions|recommendations|reports)(?:\/|$)/.test(new URL(url).pathname);
}

export function isInvestigationReadUrl(url: string, jobId: string): boolean {
  return new URL(url).pathname === `/api/v1/investigations/${jobId}`;
}

export function isInvestigationWriteUrl(url: string, method: string): boolean {
  return method === "POST" && /^\/api\/v1\/investigations(?:\/|$)/.test(new URL(url).pathname);
}

function requiredInput(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`R17 controlled resource input is unavailable: ${name}`);
  return value;
}

function requiredId(name: string): string {
  const value = requiredInput(name);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)) {
    throw new Error(`R17 controlled identifier is invalid: ${name}`);
  }
  return value.toLowerCase();
}

async function login(page: Page) {
  await page.goto("/#session");
  await page.getByLabel("用户名", { exact: true }).fill(requiredInput("DIANZI_R17_USERNAME"));
  await page.getByLabel("密码", { exact: true }).fill(requiredInput("DIANZI_R17_PASSWORD"));
  await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  await expect(page.getByLabel("密码", { exact: true })).toHaveCount(0);
  const session = await page.request.get("/v1/auth/me");
  expect(session.status()).toBe(200);
  const snapshot: unknown = await session.json();
  if (typeof snapshot !== "object" || snapshot === null || !("data_mode" in snapshot)) throw new Error("R17 server session did not confirm data mode");
  expect(snapshot.data_mode).toBe(requiredInput("DIANZI_R17_DATA_MODE"));
}

async function artifact(page: Page, info: TestInfo, name: string) {
  await page.screenshot({ path: info.outputPath(`${name}.png`), fullPage: false });
  await writeFile(info.outputPath(`${name}.json`), JSON.stringify({ observed_at: new Date().toISOString(), viewport: page.viewportSize(), actual_http: true, mocked_responses: false, external_model_source_live: "not_verified", data_mode: requiredInput("DIANZI_R17_DATA_MODE") }, null, 2));
}

test.beforeEach(() => {
  requiredInput("DIANZI_R17_FRONTEND_URL");
  if (!["live", "fixture"].includes(requiredInput("DIANZI_R17_DATA_MODE"))) throw new Error("R17 controlled data mode must be explicit");
});

test("R17 anonymous core routes, narrow keyboard access and reduced motion", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const privatePaths: string[] = [];
  page.on("request", (request) => {
    if (isPrivateWorkspaceUrl(request.url())) privatePaths.push(new URL(request.url()).pathname);
  });
  for (const route of ["events", "documents", "graph", "questions", "assets", "assessments", "investigations", "changes", "reports"]) {
    await page.goto(`/#${route}`);
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.getByRole("button", { name: "退出登录", exact: true })).toHaveCount(0);
  }
  await page.keyboard.press("Tab");
  const focusedTag = await page.evaluate(() => document.activeElement?.tagName);
  expect(["A", "BUTTON"]).toContain(focusedTag);
  const animations = await page.locator(".ambient-topology, .ambient-orbit, .ambient-light").evaluateAll((elements) => elements.map((element) => getComputedStyle(element).animationName));
  expect(animations).toEqual(["none", "none", "none"]);
  expect(privatePaths).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await artifact(page, info, "anonymous-390-reduced-motion");
});

test("R17 U02 original evidence uses the seeded fixed revision", async ({ page }, info) => {
  const eventId = requiredId("DIANZI_R17_EVENT_ID"), evidenceId = requiredId("DIANZI_R17_EVIDENCE_ID"), revisionId = requiredId("DIANZI_R17_REVISION_ID");
  await login(page);
  const loaded = page.waitForResponse((response) => new URL(response.url()).pathname === `/v1/evidence/${evidenceId}`);
  await page.goto(`/#events/${eventId}/evidence/${evidenceId}/revision/${revisionId}`);
  const response = await loaded;
  expect(response.status()).toBe(200);
  const evidence: unknown = await response.json();
  expect(evidence).toMatchObject({ span_id: evidenceId, revision_id: revisionId, data_mode: requiredInput("DIANZI_R17_DATA_MODE") });
  await expect(page.getByText(requiredInput("DIANZI_R17_EVIDENCE_QUOTE"), { exact: true }).first()).toBeVisible();
  await expect(page.locator(".evidence-inspector").getByText(revisionId, { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator(".evidence-inspector").getByText(revisionId, { exact: true })).toBeVisible();
  await artifact(page, info, "fixed-revision-evidence");
});

test("R17 U01 empty query remains distinct from a service failure", async ({ page }, info) => {
  await login(page); await page.goto("/#events");
  await expect(page.getByRole("button", { name: "检索情报", exact: true })).toBeEnabled();
  const query = requiredInput("DIANZI_R17_EMPTY_QUERY");
  await page.getByLabel("检索关键词", { exact: true }).fill(query);
  const read = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/events" && new URL(response.url()).searchParams.get("q") === query);
  await page.getByRole("button", { name: "检索情报", exact: true }).click();
  expect((await read).status()).toBe(200);
  await expect(page.getByRole("heading", { name: "本次查询没有事件记录", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "检索情报", exact: true })).toBeEnabled();
  await artifact(page, info, "actual-empty-query");
});

test("R17 loading remains visible until the original HTTP request is released", async ({ page }, info) => {
  const eventId = requiredId("DIANZI_R17_EVENT_ID");
  await login(page);
  let releaseRequest: (() => void) | undefined;
  let requestReached: (() => void) | undefined;
  const release = new Promise<void>((resolve) => { releaseRequest = resolve; });
  const reached = new Promise<void>((resolve) => { requestReached = resolve; });
  await page.route(`**/v1/events/${eventId}`, async (route) => {
    requestReached?.();
    await release;
    await route.continue();
  });
  const response = page.waitForResponse((result) => new URL(result.url()).pathname === `/v1/events/${eventId}`);
  try {
    await page.goto(`/#events/${eventId}`);
    await reached;
    await expect(page.locator(".event-detail").getByText("正在取得事件事实与历史版本…", { exact: true })).toBeVisible();
    await artifact(page, info, "actual-request-held-loading");
  } finally {
    releaseRequest?.();
  }
  expect((await response).status()).toBe(200);
  await expect(page.locator(".event-detail").getByText("正在取得事件事实与历史版本…", { exact: true })).toHaveCount(0);
});

for (const state of [
  { key: "PARTIAL", message: "本次调查仅部分完成。请一并阅读停止原因、缺失要求和未配置职责。" },
  { key: "STALE", message: "调查依赖已过期。以下内容仅供历史核查，不能确认当前结论。" },
  { key: "WAITING_APPROVAL", message: "调查正在等待人工确认。本页未提供审批接口，不会自动继续执行。" },
  { key: "FAILED", message: "调查失败。已记录的操作不代表已取得完整、有效结论。" },
] as const) {
  test(`R17 U09 restored ${state.key} task survives refresh without a new submission`, async ({ page }, info) => {
    const jobId = requiredId(`DIANZI_R17_${state.key}_JOB_ID`);
    const writes: string[] = [];
    page.on("request", (request) => { if (isInvestigationWriteUrl(request.url(), request.method())) writes.push(request.url()); });
    await login(page);
    const read = page.waitForResponse((response) => isInvestigationReadUrl(response.url(), jobId));
    await page.goto(`/#investigations/${jobId}`);
    expect((await read).status()).toBe(200);
    await expect(page.getByText(state.message, { exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByText(state.message, { exact: true })).toBeVisible();
    expect(writes).toEqual([]);
    await artifact(page, info, `restored-${state.key.toLowerCase()}`);
  });
}

test("R17 U06 real permission denial clears question inputs and retry actions", async ({ page }, info) => {
  await login(page);
  await page.goto("/#questions");
  await page.getByLabel("回答标识", { exact: true }).fill(requiredId("DIANZI_R17_DENIED_ANSWER_ID"));
  const denied = page.waitForResponse((response) => new URL(response.url()).pathname.startsWith("/v1/answers/"));
  await page.getByRole("button", { name: "查询 / 刷新回答", exact: true }).click();
  expect((await denied).status()).toBe(403);
  await expect(page.getByRole("heading", { name: "问答访问已暂停", exact: true })).toBeVisible();
  await expect(page.getByLabel("回答标识", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("你的问题", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "原样重试本轮", exact: true })).toHaveCount(0);
  await artifact(page, info, "actual-question-permission-denial");
});
