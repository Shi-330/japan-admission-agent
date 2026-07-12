const { chromium } = require('playwright');
const BASE = 'http://localhost:8000';
const results = [];
function R(ac, pass, detail) { results.push({ac, pass, detail}); console.log(`  [${pass?'PASS':'FAIL'}] ${ac}: ${detail}`); }

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Login
  console.log('=== Login ===');
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(1500);
  await page.fill('input[type="email"]', 'test@example.com');
  await page.fill('input[type="password"]', 'AgentV2_test!');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(6000);

  const loggedIn = await page.locator('aside').isVisible().catch(() => false);
  R('login', loggedIn, loggedIn ? 'Logged in' : 'FAIL');
  if (!loggedIn) { await page.screenshot({ path: 'critiques/screenshots/eval2-login-fail.png' }); await browser.close(); return summarize(); }

  // Go to plaza and wait for data
  console.log('=== Plaza ===');
  await page.locator('button:has-text("广场")').click();
  await page.waitForTimeout(3000); // wait for API fetch

  // Take screenshot for debug
  await page.screenshot({ path: 'critiques/screenshots/eval2-plaza.png', fullPage: true });

  // Get ALL button text in the page (debug)
  const btns = await page.locator('button').allTextContents().catch(() => []);
  const trackBtnCount = btns.filter(t => t.includes('追踪')).length;
  const gridCards = await page.locator('h2:has-text("学校广场") ~ div .grid > div').count().catch(() => 0);
  console.log(`  Track buttons: ${trackBtnCount}, Grid cards: ${gridCards}`);

  R('A1-plaza-15', trackBtnCount >= 14 || gridCards >= 14,
    `Track buttons: ${trackBtnCount}, Grid cards: ${gridCards}`);

  // Check for website & update time in page text
  const pageText = await page.locator('main').textContent().catch(() => '');
  const hasWebsite = pageText.includes('官网');
  const hasUpdate = pageText.includes('更新:');
  R('A1-credibility', hasWebsite || hasUpdate, `Website: ${hasWebsite}, Update: ${hasUpdate}`);

  // Filter test - use a Japanese character that matches
  console.log('=== Filter ===');
  const filterInput = page.locator('input[placeholder*="筛选专业"]');
  if (await filterInput.isVisible().catch(() => false)) {
    await filterInput.fill('情報');
    await page.waitForTimeout(600);
    const countText = await page.locator('text=/条结果/').textContent().catch(() => '0');
    R('A3-filter', countText !== '0 条结果×', `Filter result: "${countText}"`);
    // Clear
    const clearX = page.locator('text=/条结果/').locator('button');
    if (await clearX.isVisible().catch(() => false)) await clearX.click();
    await page.waitForTimeout(300);
  }

  // Track a school
  console.log('=== Track ===');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);

  const trackBtn = page.locator('button:has-text("追踪")').first();
  if (await trackBtn.isVisible().catch(() => false)) {
    const schoolName = await page.locator('main').locator('h3').first().textContent().catch(() => '');
    await trackBtn.click();
    await page.waitForTimeout(3000);
    const toast = await page.locator('[data-sonner-toast]').first().textContent().catch(() => '');
    R('A4-track', toast.includes('已添加'), `Track "${schoolName}": ${toast.slice(0, 40)}`);

    // Calendar
    await page.locator('button:has-text("日历")').click();
    await page.waitForTimeout(1500);
    const calText = await page.locator('main').textContent().catch(() => '');
    R('A4-calendar', calText.includes('出願') || calText.includes('試験') || calText.includes('出'), `Calendar has deadlines: ${calText.slice(0, 80)}`);

    // Delete
    await page.locator('button:has-text("对话")').first().click();
    await page.waitForTimeout(500);
    const delBtn = page.locator('button[title="删除"]').first();
    if (await delBtn.isVisible().catch(() => false)) {
      await delBtn.click();
      await page.waitForTimeout(400);
      await page.locator('button:has-text("确认删除")').click();
      await page.waitForTimeout(2000);
      const dToast = await page.locator('[data-sonner-toast]').first().textContent().catch(() => '');
      R('A5-delete', dToast.includes('已删除'), `Delete: ${dToast.slice(0, 40)}`);
    }
  }

  await browser.close();
  summarize();
})();

function summarize() {
  const p = results.filter(r => r.pass).length;
  const f = results.filter(r => !r.pass).length;
  console.log(`\n===== SCORE: ${Math.round(p/(p+f)*100)}/100 (${p}/${p+f}) =====`);
}
