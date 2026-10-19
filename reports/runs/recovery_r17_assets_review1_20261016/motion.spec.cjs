const { test, expect } = require('../../../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
test('独立视觉：正常背景实际推进，reduced motion 停止，390不溢出', async ({ page }, info) => {
  await page.route('**/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    const bodies = {
      '/v1/auth/me': { user_id: 'independent-synthetic-motion', tenant_id: 'independent-synthetic-tenant', role: 'analyst', permissions: ['read:asset'], permission_version: 1, data_mode: 'fixture', csrf_token: 'independent-synthetic-csrf' },
      '/v1/health/live': { status: 'live' },
      '/v1/health/ready': { status: 'ready', reason: '独立合成视觉探针，非真实后端', dependencies: {} },
      '/v1/assets': { items: [], next_cursor: null }
    };
    if (!bodies[path]) throw new Error('未预期的视觉fixture route');
    await route.fulfill({ json: bodies[path] });
  });
  await page.goto('/#assets'); await expect(page.getByText('尚无可见资产清单', { exact: true })).toBeVisible();
  const layer = page.locator('.ambient-topology');
  const state = await layer.evaluate(element => ({ name: getComputedStyle(element).animationName, play: getComputedStyle(element).animationPlayState, first: element.getAnimations()[0]?.currentTime }));
  expect(state.name).not.toBe('none'); expect(state.play).toBe('running'); expect(typeof state.first).toBe('number');
  await expect.poll(() => layer.evaluate(element => element.getAnimations()[0]?.currentTime)).toBeGreaterThan(state.first + 100);
  await page.screenshot({ path: info.outputPath('desktop-motion.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 }); await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect.poll(() => layer.evaluate(element => getComputedStyle(element).animationName)).toBe('none');
  const reduced = await layer.evaluate(element => ({ name: getComputedStyle(element).animationName, active: element.getAnimations().length }));
  expect(reduced.active).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath('mobile-reduced-motion.png'), fullPage: true });
  fs.writeFileSync(info.outputPath('motion.json'), JSON.stringify({ fixture: true, normal: state, reduced, viewport: 390 }, null, 2));
});
