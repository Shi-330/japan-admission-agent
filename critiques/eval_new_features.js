/**
 * Eval for the dashboard-reshape + outreach work (workflow output).
 * High-signal, low-fragility: observes the real /v1/greeting network response
 * (no brittle DOM selectors) and calls /v1/draft/outreach with the app's own
 * auth token via page.evaluate. Every check is guarded — never crashes, always
 * prints a score.
 */
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:8000';
const results = [];
const R = (ac, pass, detail) => { results.push({ ac, pass, detail }); console.log(`  [${pass ? 'PASS' : 'FAIL'}] ${ac}: ${detail}`); };

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  let greeting = null;
  let authHeader = '';
  page.on('request', (req) => {
    const h = req.headers()['authorization'];
    if (req.url().includes('/v1/') && h) authHeader = h; // reuse the app's real JWT
  });
  page.on('response', async (resp) => {
    if (resp.url().includes('/v1/greeting')) {
      try { greeting = await resp.json(); } catch {}
    }
  });

  // Login
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(1000);
  await page.fill('input[type="email"]', 'test@example.com');
  await page.fill('input[type="password"]', 'AgentV2_test!');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(5000);
  const loggedIn = await page.locator('aside').isVisible().catch(() => false);
  if (!loggedIn) { console.log('LOGIN FAILED'); await browser.close(); return; }
  console.log('Logged in');
  await page.waitForTimeout(1500); // let /v1/greeting fire

  // === Greeting contract: new fields present + correct shape ===
  console.log('\n--- greeting contract (when / structural_risk / gates) ---');
  try {
    if (!greeting) { R('greeting-fetch', false, 'no /v1/greeting response captured'); }
    else {
      R('when', Array.isArray(greeting.when), `when is array, len=${greeting.when?.length}`);
      const wOk = (greeting.when || []).every(w => typeof w.verdict === 'string' && 'reason' in w);
      R('when-shape', (greeting.when || []).length === 0 || wOk, 'each when has verdict+reason');
      R('structural_risk', 'structural_risk' in greeting, `present: ${JSON.stringify(greeting.structural_risk)}`);
      R('gates', Array.isArray(greeting.gates), `gates is array, len=${greeting.gates?.length}`);
    }
  } catch (e) { R('greeting', false, 'threw: ' + e.message); }

  // === Outreach endpoint: real call with app auth, verify contract + no crash ===
  console.log('\n--- POST /v1/draft/outreach ---');
  try {
    const draft = await page.evaluate(async (auth) => {
      try {
        const r = await fetch('/v1/draft/outreach', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: auth },
          body: JSON.stringify({ school: '京都大学 情报理工', professor_name: '山田太郎' }),
        });
        const j = await r.json().catch(() => ({}));
        return { status: r.status, hasJa: !!j.body_ja, hasZh: !!j.body_zh, ph: Array.isArray(j.placeholders) ? j.placeholders.length : -1 };
      } catch (e) { return { error: String(e) }; }
    }, authHeader);
    if (draft.error) R('outreach', false, 'fetch threw: ' + draft.error);
    else R('outreach', draft.status === 200 && draft.hasJa && draft.hasZh,
      `status=${draft.status} ja=${draft.hasJa} zh=${draft.hasZh} placeholders=${draft.ph}`);
  } catch (e) { R('outreach', false, 'threw: ' + e.message); }

  await browser.close();
  const p = results.filter(r => r.pass).length;
  console.log(`\n===== NEW-FEATURES: ${p}/${results.length} =====`);
  process.exit(p === results.length ? 0 : 1);
})();
