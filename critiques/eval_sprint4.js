const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:8000';
const R = (ac, pass, detail) => { results.push({ac, pass, detail}); console.log(`  [${pass?'PASS':'FAIL'}] ${ac}: ${detail}`); };
const results = [];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Login
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(1000);
  await page.fill('input[type="email"]', 'test@example.com');
  await page.fill('input[type="password"]', 'AgentV2_test!');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(5000);
  const ok = await page.locator('aside').isVisible().catch(() => false);
  if (!ok) { console.log('LOGIN FAILED'); await browser.close(); return; }
  console.log('Logged in');

  // === AC4: CN search ===
  console.log('\n--- AC4: CN Search ---');
  await page.locator('button:has-text("广场")').click();
  await page.waitForTimeout(1500);
  await page.fill('input[placeholder*="筛选专业"]', '计算机');
  await page.waitForTimeout(600);
  const filterText = await page.locator('text=/条结果/').textContent().catch(() => '0');
  const count = parseInt(filterText) || 0;
  R('AC4', count > 0, `Search "计算机": ${count} results`);

  // Clear filter
  await page.locator('button:has-text("×")').first().click();
  await page.waitForTimeout(300);

  // === AC1: Track dedup ===
  console.log('\n--- AC1: Track Dedup ---');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  const trackBtn = page.locator('button:has-text("追踪")').first();
  if (await trackBtn.isVisible().catch(() => false)) {
    await trackBtn.click();
    await page.waitForTimeout(3000);
    // After tracking, check button text changed
    const btnText = await page.locator('button:has-text("已追踪")').first().isVisible().catch(() => false);
    R('AC1', btnText, 'Button shows "已追踪" after tracking');

    // Check disabled
    const disabled = await page.locator('button:has-text("已追踪")').first().isDisabled().catch(() => true);
    R('AC1-disabled', disabled, '已追踪 button is disabled');
  }

  // === AC3: Date picker ===
  console.log('\n--- AC3: Date picker ---');
  await page.locator('button:has-text("对话")').first().click();
  await page.waitForTimeout(500);
  const addDl = page.locator('button:has-text("+ 截止日")').first();
  if (await addDl.isVisible().catch(() => false)) {
    await addDl.click();
    await page.waitForTimeout(400);
    const dateInput = await page.locator('input[type="date"]').count().catch(() => 0);
    R('AC3', dateInput > 0, `Found ${dateInput} date inputs`);
  } else {
    R('AC3', false, '+ 截止日 not found');
  }

  // === AC2: Multi-major ===
  console.log('\n--- AC2: Multi-major ---');
  await page.locator('button:has-text("+ 添加")').first().click();
  await page.waitForTimeout(400);
  const schoolInput = page.locator('input[placeholder*="学校名称"]');
  if (await schoolInput.isVisible().catch(() => false)) {
    await schoolInput.fill('京都大学 工学研究科');
    // Select stage
    await page.locator('select').last().selectOption('contacting');
    await page.locator('button:has-text("添加")').first().click();
    await page.waitForTimeout(3000);
    const sidebarText = await page.locator('aside').textContent().catch(() => '');
    const hasBoth = sidebarText.includes('工学研究科') && sidebarText.includes('情报');
    R('AC2', hasBoth, hasBoth ? 'Both schools tracked' : 'Second school not found');
  }

  await browser.close();
  const p = results.filter(r => r.pass).length;
  console.log(`\n===== SCORE: ${Math.round(p/results.length*100)}/100 (${p}/${results.length}) =====`);
})();
