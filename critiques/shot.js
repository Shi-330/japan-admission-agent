/**
 * Screenshot the UI for visual review. Saves PNGs to critiques/shots/.
 * Run via: node critiques/run_eval.cjs shot.js --no-build
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const BASE = 'http://127.0.0.1:8000';
const OUT = path.join(__dirname, 'shots');
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(OUT, '1-login.png') });

  await page.fill('input[type="email"]', 'test@example.com');
  await page.fill('input[type="password"]', 'AgentV2_test!');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(5000);
  if (!(await page.locator('aside').isVisible().catch(() => false))) {
    console.log('LOGIN FAILED'); await browser.close(); return;
  }
  console.log('Logged in');
  await page.waitForTimeout(2500); // dashboard + greeting render

  await page.screenshot({ path: path.join(OUT, '2-dashboard.png'), fullPage: true });
  console.log('shot: dashboard (fullPage)');

  // Outreach draft dialog (if a tracked professor exists in the sidebar)
  try {
    const btn = page.locator('button[title="生成套磁邮件草稿"]').first();
    if (await btn.isVisible().catch(() => false)) {
      await btn.click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: path.join(OUT, '3-outreach-loading.png') });
      await page.waitForTimeout(9000); // LLM draft generation
      await page.screenshot({ path: path.join(OUT, '4-outreach-draft.png') });
      console.log('shot: outreach draft');
    } else {
      console.log('no professor outreach button in sidebar — skipping outreach shots');
    }
  } catch (e) { console.log('outreach shot failed: ' + e.message); }

  await browser.close();
  console.log('done. shots in critiques/shots/');
})();
