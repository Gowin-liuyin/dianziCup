process.env.PLAYWRIGHT_BROWSERS_PATH = process.argv[2];
const { chromium } = await import("../../../frontend/node_modules/@playwright/test/index.mjs");
const headless = process.argv[3] !== "headed";
const browser = await chromium.launch({ headless, ...(headless ? {} : { channel: "msedge", ignoreDefaultArgs: ["--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding", "--disable-background-timer-throttling"] }) });
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(process.argv[4] ?? "data:text/html,<title>Visibility Probe</title><h1>Temporary visibility probe</h1>");
  const initial = await page.evaluate(() => document.visibilityState);
  const otherPage = await context.newPage();
  await otherPage.bringToFront();
  const afterNewTab = await page.evaluate(() => document.visibilityState);
  const background = async () => page.evaluate(() => ({ visibility: document.visibilityState, paused: document.querySelector(".ambient-backdrop")?.getAttribute("data-paused"), animation: document.querySelector(".ambient-topology") ? getComputedStyle(document.querySelector(".ambient-topology")).animationPlayState : null }));
  const session = await context.newCDPSession(page);
  await session.send("Emulation.setFocusEmulationEnabled", { enabled: false });
  const otherSession = await context.newCDPSession(otherPage);
  await otherSession.send("Emulation.setFocusEmulationEnabled", { enabled: false });
  await otherPage.bringToFront();
  await otherPage.waitForTimeout(150);
  const afterDisablingEmulation = await background();
  let afterMinimize = null;
  if (!headless) {
    const window = await session.send("Browser.getWindowForTarget");
    await session.send("Browser.setWindowBounds", { windowId: window.windowId, bounds: { windowState: "minimized" } });
    await otherPage.waitForTimeout(300);
    afterMinimize = await background();
  }
  await session.send("Page.setWebLifecycleState", { state: "frozen" });
  await session.send("Page.setWebLifecycleState", { state: "active" });
  const afterLifecycle = await page.evaluate(() => document.visibilityState);
  console.log(JSON.stringify({ initial, afterNewTab, afterDisablingEmulation, afterMinimize, afterLifecycle, browserVersion: browser.version(), mode: headless ? "headless" : "headed", target: process.argv[4] ?? "temporary data: page; no credentials or product state" }));
} finally {
  await browser.close();
}
