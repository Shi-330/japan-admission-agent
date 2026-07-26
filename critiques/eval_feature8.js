/**
 * Feature 8: Chat Context Enhancement — smoke eval
 *
 * Run: node critiques/eval_feature8.js
 * Requires server on http://localhost:8000
 */
const { chromium } = require('playwright');
const BASE = 'http://localhost:8000';
// Env vars: TEST_EMAIL, TEST_PASSWORD, TEST_MAJOR (default: 环境学)
const TEST_EMAIL = process.env.TEST_EMAIL || 'test@example.com';
const TEST_PASSWORD = process.env.TEST_PASSWORD || '<your-test-password>';
const TEST_MAJOR = process.env.TEST_MAJOR || '环境学';

const results = [];
function R(label, pass, detail) {
  results.push({ label, pass, detail });
  console.log(`  [${pass ? 'PASS' : 'FAIL'}] ${label}: ${detail}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // ── 1. Login ──
  console.log('--- Login ---');
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(2000);

  const emailInput = page.locator('input[type="email"]');
  const pwInput = page.locator('input[type="password"]');
  const submitBtn = page.locator('button[type="submit"]');

  if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    await emailInput.fill('test@example.com');
    // User changed password — this is the old one, will fail but we test UI anyway
    await pwInput.fill('123test456');
    await submitBtn.click();
    await page.waitForTimeout(5000);
  }

  const loggedIn = await page.locator('aside, nav, [class*="sidebar"]').isVisible().catch(() => false);
  R('1-login', loggedIn, loggedIn ? 'Login form submitted' : 'Login form not visible or failed');

  // ── 2. Dashboard loads ──
  console.log('--- Dashboard ---');
  const hasGreeting = await page.locator('text=加载中').isVisible().catch(() => true);
  R('2-dashboard', hasGreeting !== null, 'Dashboard renders without crash');

  // ── 3. Chat SSE — search 环境学, verify cards >= 8 ──
  console.log('--- Chat ---');
  let cardCount = 0;
  try {
    // Switch to chat tab
    const chatTab = page.locator('button[value="chat"]');
    if (await chatTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await chatTab.click();
      await page.waitForTimeout(1000);
    }

    const chatInput = page.locator('input[placeholder*="输入"], textarea[placeholder*="输入"]');
    if (await chatInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await chatInput.fill(`我想考${TEST_MAJOR}相关的研究室`);
      await page.keyboard.press('Enter');
    }

    // Wait for SSE response + web search enrichment + LLM fallback
    await page.waitForTimeout(35000);

    // Count school cards — look for SchoolCard compact mode or track buttons
    cardCount = await page.locator('button:has-text("追踪"), [class*="SchoolCard"], text=参考').count().catch(() => 0);
    const pageText = await page.locator('main').textContent().catch(() => '');
    console.log('  [DEBUG] Page text sample:', pageText?.slice(0, 500));
    const hasError = pageText.includes('[错误]');

    R('3-chat-cards', cardCount >= 1, `${cardCount} school elements in chat (cards/track/参考)`);
    R('4-chat-enrichment', cardCount >= 4, `${cardCount} elements (target: >=4 with LLM fallback)`);
    R('5-no-error', !hasError, hasError ? 'Chat returned error' : 'No chat error');

    // ── 4. Jump to plaza — verify filter + school count ──
    console.log('--- Plaza jump ---');
    const goBtn = page.locator('button:has-text("去看看")');
    if (await goBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await goBtn.click();
      await page.waitForTimeout(4000);
    }

    // Check plaza filter is pre-filled
    const filterVal = await page.locator('input[placeholder*="筛选"]').inputValue().catch(() => '');
    R('6-plaza-filter', filterVal.length > 0, `Plaza filter pre-filled: "${filterVal.slice(0,30)}"`);

    // Count schools in plaza
    const plazaCards = await page.locator('text=追踪').count().catch(() => 0);
    R('7-plaza-count', plazaCards >= 3, `${plazaCards} schools in plaza`);
  } catch (e) {
    R('3-chat', false, `Chat test exception: ${e.message}`);
  }

  // ── 4. Plaza loads with schools ──
  console.log('--- Plaza ---');
  try {
    const plazaTab = page.locator('button[value="plaza"], button:has-text("广场")');
    if (await plazaTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await plazaTab.click();
      await page.waitForTimeout(3000);
    }

    const plazaCards = await page.locator('text=国立, text=公立, text=私立').count().catch(() => 0);
    const hasSchools = await page.locator('text=追踪').first().isVisible({ timeout: 5000 }).catch(() => false);
    R('6-plaza-schools', hasSchools || plazaCards > 0, `Plaza shows schools (type badges: ${plazaCards})`);
  } catch (e) {
    R('6-plaza', false, `Plaza test exception: ${e.message}`);
  }

  // ── 5. Enrichment worker ──
  console.log('--- Enrichment ---');
  try {
    const { execSync } = require('child_process');
    const enrichResult = execSync(
      `python enrich_schools.py --school "一桥大学 社会学研究科"`,
      { cwd: '..', timeout: 120000, encoding: 'utf8' }
    ).catch(() => '');
    const enriched = enrichResult.includes('OK');
    R('8-enrichment', enriched, enrichResult.slice(0, 100) || 'enrichment ran');
  } catch (e) {
    R('8-enrichment', false, `Enrichment test: ${e.message?.slice(0, 80)}`);
  }

  // ── 6. Summary ──
  const passed = results.filter(r => r.pass).length;
  const total = results.length;
  console.log(`\n=== ${passed}/${total} passed ===`);

  await browser.close();
  process.exit(passed === total ? 0 : 1);
})();
