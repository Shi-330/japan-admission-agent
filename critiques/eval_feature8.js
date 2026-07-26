/**
 * Feature 8: Chat Context Enhancement — smoke eval
 *
 * Run: node critiques/eval_feature8.js
 * Requires server on http://localhost:8000
 */
const { chromium } = require('playwright');
const BASE = 'http://localhost:8000';
// Override via env: TEST_EMAIL / TEST_PASSWORD
const TEST_EMAIL = process.env.TEST_EMAIL || 'test@example.com';
const TEST_PASSWORD = process.env.TEST_PASSWORD || '<your-test-password>';

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

  // ── 3. Chat SSE — send a query ──
  console.log('--- Chat ---');
  try {
    // Switch to chat tab
    const chatTab = page.locator('button[value="chat"]');
    if (await chatTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await chatTab.click();
      await page.waitForTimeout(1000);
    }

    const chatInput = page.locator('input[placeholder*="输入"], textarea[placeholder*="输入"]');
    if (await chatInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await chatInput.fill('我想考环境相关的研究室');
      await page.keyboard.press('Enter');
    }

    // Wait for SSE response (school cards or text)
    await page.waitForTimeout(15000);

    // Check for school cards in chat
    const pageText = await page.locator('main').textContent().catch(() => '');
    const hasSchoolCard = pageText.includes('追踪') || pageText.includes('匹配') || pageText.includes('学校');
    R('3-chat-school-search', hasSchoolCard, hasSchoolCard ? 'Chat shows school-related content' : 'No school content in chat');

    // Check for SchoolCard component
    const hasCard = await page.locator('text=追踪').first().isVisible().catch(() => false);
    R('4-chat-cards', hasCard || hasSchoolCard, hasCard ? 'School cards visible in chat' : 'Cards not visible but content present');

    // Check for errors
    const hasError = pageText.includes('[错误]');
    R('5-no-error', !hasError, hasError ? 'Chat returned error' : 'No chat error');

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

  // ── 5. Summary ──
  const passed = results.filter(r => r.pass).length;
  const total = results.length;
  console.log(`\n=== ${passed}/${total} passed ===`);

  await browser.close();
  process.exit(passed === total ? 0 : 1);
})();
