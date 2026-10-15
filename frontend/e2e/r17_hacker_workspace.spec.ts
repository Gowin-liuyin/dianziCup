import process from "node:process";
import { expect, test, type Page } from "@playwright/test";

async function loginToIsolatedApi(page: Page) {
  const username = process.env.DIANZI_E2E_USERNAME;
  const password = process.env.DIANZI_E2E_PASSWORD;
  if (!username || !password) throw new Error("Isolated real API credentials must be injected by the controlled runner");
  await page.goto("/");
  await page.getByLabel("用户名", { exact: true }).fill(username);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
}

test("R17-C01/C04 real auth, research navigation and explanatory unavailable states", async ({ page }, testInfo) => {
  await loginToIsolatedApi(page);
  await expect(page.getByRole("table", { name: "实际依赖探测结果" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("hacker-runtime-real-api-1280.png"), fullPage: true });
  await page.getByRole("link", { name: "情报列表", exact: true }).click();
  await expect(page.getByRole("heading", { name: "情报工作区", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "检索情报", exact: true })).toBeDisabled();
  await expect(page.getByText("情报服务待接通", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "证据检视", exact: true })).toBeVisible();
  await expect(page.getByText("暂无风险", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "情报工作区", exact: true })).toBeVisible();
  await expect(page.getByText("真实 / Live", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("hacker-events-preparation-1280.png"), fullPage: true });
  for (const [label, title] of [["来源监测", "来源与采集"], ["知识图谱", "关联研究"], ["引用问答", "证据问答"], ["资产自查", "版本与资产"], ["任务轨迹", "调查与任务"], ["变化与推荐", "变化与关注"], ["证据报告", "报告与交付"]]) {
    await page.getByRole("link", { name: label, exact: true }).click();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await expect(page.getByText("本页能力待接通", { exact: true })).toBeVisible();
  }
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeEnabled();
  await expect(page.getByText("已授予权限", { exact: true })).toHaveCount(0);
});

test("R17-C05/C06 390px navigation, keyboard and reduced motion with real API", async ({ page }, testInfo) => {
  await loginToIsolatedApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const label of ["情报列表", "来源监测", "知识图谱", "引用问答", "资产自查", "任务轨迹", "变化与推荐", "证据报告", "运行状态", "会话与权限"]) {
    const navigation = page.getByRole("link", { name: label, exact: true });
    await navigation.focus();
    await page.keyboard.press("Enter");
    await expect(navigation).toHaveAttribute("aria-current", "page");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.getByRole("link", { name: "情报列表", exact: true }).click();
  const description = page.getByText("尚未取得事件查询结果。接通真实来源与事件服务后，可查看记录、修订与证据；当前不能判断为无情报。", { exact: true });
  expect(await description.evaluate((element) => {
    const range = document.createRange();
    range.selectNodeContents(element);
    return [...range.getClientRects()].every((rectangle) => rectangle.left >= 0 && rectangle.right <= window.innerWidth);
  })).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("hacker-events-preparation-390.png"), fullPage: true });
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeEnabled();
});

test("R17 dynamic background moves without layout shifts and reduced motion stops it", async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/#events");
  await expect(page.getByText("情报服务待接通", { exact: true })).toBeVisible();
  const motion = page.getByTestId("ambient-motion");
  const initial = await motion.evaluate((element) => ({ transform: getComputedStyle(element).transform, animation: getComputedStyle(element).animationName, state: getComputedStyle(element).animationPlayState }));
  expect(initial.animation).toBe("topology-drift");
  expect(initial.state).toBe("running");
  const mainBounds = await page.locator("#main-content").boundingBox();
  await page.evaluate(() => {
    performance.clearMarks();
    performance.mark("ambient-check-start");
  });
  await page.screenshot({ path: testInfo.outputPath("ambient-frame-a.png"), fullPage: false });
  await expect.poll(() => motion.evaluate((element) => getComputedStyle(element).transform)).not.toBe(initial.transform);
  const frameObservation = await page.evaluate(() => new Promise<{ frameCount: number; durationMilliseconds: number; p95FrameMilliseconds: number; maximumFrameMilliseconds: number; longTaskCount: number }>((resolve) => {
    const frameIntervals: number[] = [];
    let lastFrame: number | null = null;
    let longTaskCount = 0;
    const observer = new PerformanceObserver((entries) => { longTaskCount += entries.getEntries().length; });
    observer.observe({ type: "longtask" });
    const sampleFrame = (timestamp: number) => {
      if (lastFrame !== null) frameIntervals.push(timestamp - lastFrame);
      lastFrame = timestamp;
      if (frameIntervals.length < 60) { requestAnimationFrame(sampleFrame); return; }
      observer.disconnect();
      const ordered = [...frameIntervals].sort((left, right) => left - right);
      resolve({ frameCount: frameIntervals.length, durationMilliseconds: frameIntervals.reduce((total, interval) => total + interval, 0), p95FrameMilliseconds: ordered[Math.ceil(ordered.length * .95) - 1] ?? 0, maximumFrameMilliseconds: ordered.at(-1) ?? 0, longTaskCount });
    };
    requestAnimationFrame(sampleFrame);
  }));
  await page.screenshot({ path: testInfo.outputPath("ambient-frame-b.png"), fullPage: false });
  expect(await page.locator("#main-content").boundingBox()).toEqual(mainBounds);
  const observed = await page.evaluate(() => ({ observationMilliseconds: performance.now() - (performance.getEntriesByName("ambient-check-start")[0]?.startTime ?? performance.now()), domElements: document.getElementsByTagName("*").length, backgroundElements: document.querySelectorAll(".ambient-backdrop *").length, pointerEvents: getComputedStyle(document.querySelector(".ambient-backdrop") ?? document.body).pointerEvents }));
  expect(observed.pointerEvents).toBe("none");
  expect(observed.backgroundElements).toBeLessThan(20);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect.poll(() => motion.evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  await page.getByRole("link", { name: "运行状态", exact: true }).click();
  await expect(page.getByRole("button", { name: "刷新状态", exact: true })).toBeEnabled();
  await testInfo.attach("ambient-observation", { body: JSON.stringify({ initial, observed, frameObservation, layoutUnchanged: true, reducedMotionAnimationName: await motion.evaluate((element) => getComputedStyle(element).animationName) }), contentType: "application/json" });
});
