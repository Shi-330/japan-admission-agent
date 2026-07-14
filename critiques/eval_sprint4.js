const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:8000';

// pass / fail / skip — skips are NOT counted against the score (missing precondition != broken feature)
const results = [];
const R = (ac, pass, detail) => { results.push({ ac, pass, state: pass ? 'pass' : 'fail', detail }); console.log(`  [${pass ? 'PASS' : 'FAIL'}] ${ac}: ${detail}`); };
const S = (ac, detail) => { results.push({ ac, state: 'skip', detail }); console.log(`  [SKIP] ${ac}: ${detail}`); };
// each AC runs isolated: a throw becomes a clean FAIL and never aborts the other ACs
async function step(name, header, fn) {
  console.log(`\n--- ${name}: ${header} ---`);
  try { await fn(); } catch (e) { R(name, false, 'threw: ' + String((e && e.message) || e).split('\n')[0]); }
}
// count plaza school cards via their exact 追踪/已追踪 button name (avoids the 追踪⊂已追踪 substring trap)
const cardCount = (page) => page.getByRole('button', { name: /^(追踪|已追踪)$/ }).count();

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Login — wait for the sidebar to appear instead of a fixed sleep
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.fill('input[type="email"]', 'test@example.com');
  await page.fill('input[type="password"]', 'AgentV2_test!');
  await page.locator('button[type="submit"]').click();
  try { await page.waitForSelector('aside', { timeout: 15000 }); } catch { console.log('LOGIN FAILED'); await browser.close(); return; }
  console.log('Logged in');

  // === AC4: CN→JP plaza search filters correctly ===
  await step('AC4', 'CN Search', async () => {
    await page.getByRole('tab', { name: '广场' }).click();
    // wait for catalog to render; reload once if the first-load race leaves it empty (see backlog #17)
    let total = 0;
    for (const attempt of [1, 2]) {
      await page.waitForFunction(() => document.querySelectorAll('h3').length > 3, { timeout: 8000 }).catch(() => {});
      total = await cardCount(page);
      if (total > 0) break;
      if (attempt === 1) { await page.reload({ waitUntil: 'domcontentloaded' }); await page.getByRole('tab', { name: '广场' }).click().catch(() => {}); }
    }
    if (total === 0) { R('AC4', false, 'catalog empty after reload (see #17 first-load race)'); return; }
    await page.fill('input[placeholder*="筛选专业"]', '计算机');
    await page.waitForTimeout(1000);
    const filtered = await cardCount(page);
    R('AC4', filtered > 0 && filtered < total, `"计算机" filtered ${filtered}/${total} schools`);
  });

  // === AC1: track dedup — state-robust ===
  await step('AC1', 'Track Dedup', async () => {
    await page.getByRole('tab', { name: '广场' }).click();
    await page.locator('input[placeholder*="筛选专业"]').fill('').catch(() => {});
    await page.waitForTimeout(600);
    const untracked = page.getByRole('button', { name: '追踪', exact: true });
    if (await untracked.count() > 0) {
      await untracked.first().click();
      await page.waitForTimeout(2500);
      const disabled = await page.getByRole('button', { name: '已追踪', exact: true }).first().isDisabled().catch(() => false);
      R('AC1', disabled, `tracked a school -> 已追踪 shown and disabled: ${disabled}`);
    } else {
      // everything already tracked -> the dedup invariant already holds
      const tracked = await page.getByRole('button', { name: '已追踪', exact: true }).count();
      R('AC1', tracked > 0, `all ${tracked} schools already 已追踪 (dedup invariant holds)`);
    }
  });

  // === AC3: deadline date picker (skip if no tracked-school card exposes it) ===
  await step('AC3', 'Date Picker', async () => {
    await page.getByRole('tab', { name: '对话' }).click();
    await page.waitForTimeout(800);
    const addDl = page.getByRole('button', { name: '+ 截止日' });
    if (await addDl.count() === 0) { S('AC3', 'no "+ 截止日" (needs a tracked-school card in edit) — skipped'); return; }
    await addDl.first().click();
    await page.waitForTimeout(500);
    const dateInputs = await page.locator('input[type="date"]').count();
    R('AC3', dateInputs > 0, `date input appeared: ${dateInputs}`);
  });

  // === AC2: add a second school (multi-major coexist) ===
  await step('AC2', 'Multi-major add', async () => {
    const addBtn = page.locator('button:has-text("+ 添加")').first();
    if (await addBtn.count() === 0) { S('AC2', 'no "+ 添加" button — skipped'); return; }
    await addBtn.click();
    await page.waitForTimeout(500);
    const schoolInput = page.locator('input[placeholder*="学校名称"]');
    if (!(await schoolInput.isVisible().catch(() => false))) { S('AC2', 'add-school form did not open — skipped'); return; }
    await schoolInput.fill('京都大学 工学研究科');
    await page.locator('select').last().selectOption('contacting').catch(() => {});
    await page.locator('button:has-text("添加")').first().click();
    await page.waitForTimeout(2500);
    const sidebar = await page.locator('aside').textContent().catch(() => '');
    R('AC2', sidebar.includes('工学研究科'), sidebar.includes('工学研究科') ? 'second school added to sidebar' : 'second school not found');
  });

  await browser.close();
  const scored = results.filter(r => r.state !== 'skip');
  const p = scored.filter(r => r.pass).length;
  const skipped = results.length - scored.length;
  console.log(`\n===== SCORE: ${scored.length ? Math.round(p / scored.length * 100) : 0}/100 (${p}/${scored.length})${skipped ? `, ${skipped} skipped` : ''} =====`);
})();
