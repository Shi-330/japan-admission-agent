// Shared eval auth helper: login ONCE per origin, cache Playwright storageState,
// reuse it across eval scripts and runs until the JWT nears expiry (~1h).
// Usage:
//   const { getAuthedPage } = require('./eval_helpers.cjs');
//   const { browser, page } = await getAuthedPage('http://localhost:8100');
//   ... assertions ...
//   await browser.close();
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const STATE_MAX_AGE_MIN = 50; // Supabase access tokens live ~60min; refresh before the edge
const CREDS = { email: 'test@example.com', password: 'AgentV2_test!' };

// storageState (incl. localStorage jwt) is per-origin, so key the cache file by port
function stateFile(baseURL) {
  const port = new URL(baseURL).port || '80';
  return path.join(__dirname, `.auth-state-${port}.json`);
}

async function getAuthedPage(baseURL, creds = CREDS) {
  const browser = await chromium.launch({ headless: true });
  const state = stateFile(baseURL);

  // Fast path: reuse cached auth state if it is fresh enough
  const fresh = fs.existsSync(state) && Date.now() - fs.statSync(state).mtimeMs < STATE_MAX_AGE_MIN * 60 * 1000;
  if (fresh) {
    const ctx = await browser.newContext({ baseURL, storageState: state });
    const page = await ctx.newPage();
    await page.goto('/');
    // Logged-in check: password field absent means the app skipped the login screen
    try {
      await page.waitForSelector('input[type="password"], [role="tablist"]', { timeout: 10000 });
      if ((await page.locator('input[type="password"]').count()) === 0) {
        return { browser, ctx, page };
      }
    } catch { /* fall through to full login */ }
    await ctx.close();
  }

  // Slow path: full login, then persist state for every later script/run
  const ctx = await browser.newContext({ baseURL });
  const page = await ctx.newPage();
  await page.goto('/');
  await page.waitForSelector('input[type="email"]', { timeout: 15000 });
  await page.locator('input[type="email"]').fill(creds.email);
  await page.locator('input[type="password"]').fill(creds.password);
  await page.locator('button:has-text("登录")').last().click();
  await page.waitForSelector('input[type="password"]', { state: 'detached', timeout: 20000 });
  await ctx.storageState({ path: state });
  return { browser, ctx, page };
}

module.exports = { getAuthedPage, stateFile, CREDS };
