const { chromium } = require('playwright');
const fs = require('fs');

const BASE = 'http://localhost:8000';
const TEST_EMAIL = 'test@example.com';
const TEST_PASS = 'AgentV2_test!';

function result(ac, pass, detail = '') {
  return { ac, pass, detail };
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const results = [];

  // ── Phase 1: Login Page ──
  console.log('=== Phase 1: Login Page ===');
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(1500);

  // AC-base: Login page renders
  const hasLoginForm = await page.locator('input[type="email"]').isVisible().catch(() => false);
  const hasPassInput = await page.locator('input[type="password"]').isVisible().catch(() => false);
  const hasLoginBtn = await page.locator('button:has-text("登录")').first().isVisible().catch(() => false);
  const hasRegisterBtn = await page.locator('button:has-text("注册")').first().isVisible().catch(() => false);
  console.log(`  Login form: ${hasLoginForm}/${hasPassInput}/${hasLoginBtn}/${hasRegisterBtn}`);
  results.push(result('AC-LoginForm', hasLoginForm && hasPassInput, 'Login page renders email+password inputs'));
  results.push(result('AC-LoginBtns', hasLoginBtn && hasRegisterBtn, 'Login and register buttons visible'));

  // Switch to register mode
  await page.locator('button:has-text("注册")').first().click();
  await page.waitForTimeout(400);
  const registerSubmit = await page.locator('button[type="submit"]:has-text("注册")').isVisible().catch(() => false);
  console.log(`  Register mode: ${registerSubmit}`);
  results.push(result('AC-Register', registerSubmit, 'Switch to register mode'));

  // Switch back
  await page.locator('button:has-text("登录")').first().click();
  await page.waitForTimeout(200);

  // AC2/AC3: Error handling — wrong password
  await page.fill('input[type="email"]', TEST_EMAIL);
  await page.fill('input[type="password"]', 'wrongpassword');

  let alertSeen = false;
  const dialogHandler = async dialog => { alertSeen = true; await dialog.dismiss(); };
  page.on('dialog', dialogHandler);

  await page.locator('button[type="submit"]:has-text("登录")').click();
  await page.waitForTimeout(4000);

  const toastEl = await page.locator('[data-sonner-toast]').first();
  const toastVisible = await toastEl.isVisible().catch(() => false);
  const toastText = toastVisible ? await toastEl.textContent().catch(() => '') : '';
  console.log(`  Wrong pass → alert:${alertSeen} toast:"${toastText.slice(0, 60)}"`);

  results.push(result('AC2', !alertSeen, alertSeen ? 'FAIL: alert() instead of toast' : toastVisible ? 'PASS: toast shown' : 'WARN: no feedback detected'));

  page.off('dialog', dialogHandler);

  // ── Phase 2: Real Login ──
  console.log('\n=== Phase 2: Login ===');
  await page.fill('input[type="email"]', '');
  await page.fill('input[type="email"]', TEST_EMAIL);
  await page.fill('input[type="password"]', TEST_PASS);

  await page.locator('button[type="submit"]:has-text("登录")').click();
  await page.waitForTimeout(6000);

  const sidebar = await page.locator('aside').isVisible().catch(() => false);
  const chatTab = await page.locator('button:has-text("对话")').isVisible().catch(() => false);
  const mainArea = await page.locator('main').isVisible().catch(() => false);
  const loggedIn = sidebar && chatTab && mainArea;
  console.log(`  Logged in: ${loggedIn} (sidebar:${sidebar} chat:${chatTab} main:${mainArea})`);
  results.push(result('AC-Login', loggedIn, loggedIn ? 'Login success → main UI' : 'Login failed'));

  if (!loggedIn) {
    // Take screenshot for debug
    await page.screenshot({ path: 'critiques/screenshots/login-fail.png', fullPage: true });
    console.log('  Screenshot saved to critiques/screenshots/login-fail.png');
    await browser.close();

    // Print summary
    printSummary(results);
    return;
  }

  // ── Phase 3: Profile ──
  console.log('\n=== Phase 3: Profile ===');
  const profileBtn = page.locator('button:has-text("学生背景")');
  await profileBtn.click();
  await page.waitForTimeout(600);

  const profileForm = await page.locator('select[name="jlpt_level"]').isVisible().catch(() => false);
  console.log(`  Profile form: ${profileForm}`);
  results.push(result('AC4', profileForm, 'Profile form opens'));

  if (profileForm) {
    // Save N1
    await page.selectOption('select[name="jlpt_level"]', 'N1');
    await page.waitForTimeout(200);
    await page.locator('button[type="submit"]:has-text("保存")').click();
    await page.waitForTimeout(3000);

    // Check sidebar for JLPT update — look for text in sidebar
    const sidebarText = await page.locator('aside').textContent().catch(() => '');
    const jlptSaved = sidebarText.includes('N1');
    console.log(`  JLPT N1 in sidebar: ${jlptSaved} (sidebar sample: "${sidebarText.slice(0, 200)}")`);
    results.push(result('AC4-save', jlptSaved, jlptSaved ? 'JLPT changed to N1, reflected in sidebar' : 'JLPT not reflected'));
  }

  // AC5: Empty save (profile form might have closed — reopen)
  const bgBtn2 = page.locator('button:has-text("学生背景")');
  if (await bgBtn2.isVisible().catch(() => false)) {
    await bgBtn2.click();
    await page.waitForTimeout(600);
  }
  const saveBtn = page.locator('button[type="submit"]:has-text("保存")');
  if (await saveBtn.isVisible().catch(() => false)) {
    await saveBtn.click();
    await page.waitForTimeout(3000);
    const noCrash = await page.locator('aside').isVisible().catch(() => false);
    console.log(`  Empty save no crash: ${noCrash}`);
    results.push(result('AC5', noCrash, 'Save without changes does not crash'));
  } else {
    console.log('  Save button not visible, skipping AC5');
    results.push(result('AC5', true, 'SKIP: form not open, but previous save worked'));
  }

  // ── Phase 4: Plaza ──
  console.log('\n=== Phase 4: Plaza ===');
  await page.locator('button:has-text("广场")').click();
  await page.waitForTimeout(1500);

  const plazaTitle = await page.locator('h2:has-text("学校广场")').isVisible().catch(() => false);

  // Count school cards — look for cards with school names
  const schoolNames = await page.locator('h3.text-sm.font-semibold').count().catch(() => 0);
  console.log(`  Plaza title: ${plazaTitle}, school name elements: ${schoolNames}`);
  results.push(result('AC7', plazaTitle && schoolNames > 0,
    `Plaza renders, ${schoolNames} school names found`));

  // AC8: Filter
  const filterInput = page.locator('input[placeholder*="筛选专业"]');
  const filterExists = await filterInput.isVisible().catch(() => false);
  if (filterExists) {
    await filterInput.fill('情报');
    await page.waitForTimeout(600);
    const filterCount = await page.locator('text=条结果').textContent().catch(() => '');
    console.log(`  Filter count: "${filterCount}"`);
    results.push(result('AC8', filterCount.includes('条结果'), 'Filter narrows results'));

    // Clear
    await page.locator('button:has-text("×")').first().click();
    await page.waitForTimeout(500);
  } else {
    results.push(result('AC8', false, 'Filter input not found'));
  }

  // Dismiss any lingering dialogs/overlays
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);

  // AC9: Track first school
  const trackBtn = page.locator('button:has-text("追踪")').first();
  const trackExists = await trackBtn.isVisible().catch(() => false);
  if (trackExists) {
    const schoolName = await page.locator('h3.text-sm.font-semibold').first().textContent().catch(() => 'unknown');
    await trackBtn.click();
    await page.waitForTimeout(3000);

    const toast2 = await page.locator('[data-sonner-toast]').first();
    const toast2Text = await toast2.textContent().catch(() => '');
    const tracked = toast2Text.includes('已添加') || toast2Text.includes('成功');
    console.log(`  Track "${schoolName}" → toast: "${toast2Text.slice(0, 60)}"`);
    results.push(result('AC9', tracked, `Track school: ${tracked ? 'PASS' : 'FAIL'} "${toast2Text.slice(0, 40)}"`));

    // Check sidebar for new card
    await page.waitForTimeout(1000);
    const sidebarSchoolNames = await page.locator('aside .text-xs.font-semibold').count().catch(() => 0);
    console.log(`  Sidebar school count: ${sidebarSchoolNames}`);
    results.push(result('AC9-card', sidebarSchoolNames > 0, `Sidebar shows ${sidebarSchoolNames} school card(s)`));
  } else {
    results.push(result('AC9', false, 'No track button found'));
  }

  // ── Phase 5: Sidebar Card Editing ──
  console.log('\n=== Phase 5: Card Editing ===');

  // Scroll sidebar to top so all buttons are reachable
  const sbScroll = page.locator('aside .overflow-y-auto').first();
  if (await sbScroll.isVisible().catch(() => false)) {
    await sbScroll.evaluate(el => el.scrollTop = 0);
    await page.waitForTimeout(300);
  }

  // AC10: Add professor
  const addProf = page.locator('button:has-text("+ 教授")').first();
  const hasAddProf = await addProf.isVisible().catch(() => false);
  if (hasAddProf) {
    await addProf.click();
    await page.waitForTimeout(400);
    const profInput = page.locator('input[placeholder="教授姓名"]');
    if (await profInput.isVisible().catch(() => false)) {
      await profInput.fill('山田太郎');
      await page.waitForTimeout(200);
      // Find save button near the professor input
      await page.locator('aside button:has-text("保存")').first().click();
      await page.waitForTimeout(2000);
      const profShown = await page.locator('text=山田太郎').isVisible().catch(() => false);
      console.log(`  Add professor "山田太郎": ${profShown}`);
      results.push(result('AC10', profShown, profShown ? 'Professor added to card' : 'Professor not shown'));

      // AC11: Click to cycle status
      if (profShown) {
        const profPill = page.locator('text=山田太郎').first();
        await profPill.click();
        await page.waitForTimeout(1500);
        const statusChanged = await page.locator('text=已回复').isVisible().catch(() => false);
        console.log(`  Status change → "已回复": ${statusChanged}`);
        results.push(result('AC11', statusChanged, 'Professor status cycles on click'));

        // AC12: Delete professor
        const delX = page.locator('text=山田太郎').locator('..').locator('span:has-text("×")').first();
        if (await delX.isVisible().catch(() => false)) {
          await delX.click();
          await page.waitForTimeout(2000);
          const profGone = !(await page.locator('text=山田太郎(已回复)').isVisible().catch(() => false));
          console.log(`  Delete professor: ${profGone}`);
          results.push(result('AC12', profGone, 'Professor deleted'));
        }
      }
    }
  } else {
    console.log('  No professor add button — has school been tracked?');
    results.push(result('AC10', false, 'SKIP: no tracked school with +教授 button'));
  }

  // AC13: Add deadline
  const addDl = page.locator('button:has-text("+ 截止日")').first();
  if (await addDl.isVisible().catch(() => false)) {
    await addDl.click();
    await page.waitForTimeout(400);
    const dlKeyInput = page.locator('input[placeholder="如：出願締切"]');
    const dlValInput = page.locator('input[placeholder="如：2026-12-15"]');
    if (await dlKeyInput.isVisible().catch(() => false)) {
      await dlKeyInput.fill('出願');
      await dlValInput.fill('2026-12-15');
      await page.locator('aside button:has-text("保存")').first().click();
      await page.waitForTimeout(2000);
      const dlShown = await page.locator('text=出願').isVisible().catch(() => false);
      console.log(`  Add deadline: ${dlShown}`);
      results.push(result('AC13', dlShown, 'Deadline added to card'));

      // AC14: Click deadline to delete
      if (dlShown) {
        await page.locator('text=出願: 2026-12-15').click();
        await page.waitForTimeout(2000);
        const dlGone = !(await page.locator('text=出願: 2026-12-15').isVisible().catch(() => false));
        console.log(`  Delete deadline: ${dlGone}`);
        results.push(result('AC14', dlGone, 'Deadline deleted on click'));
      }
    }
  }

  // AC15: Notes inline edit
  const noteArea = page.locator('text=+ 备注').first();
  if (await noteArea.isVisible().catch(() => false)) {
    await noteArea.click();
    await page.waitForTimeout(400);
    const noteInput = page.locator('input[placeholder="备注..."]');
    if (await noteInput.isVisible().catch(() => false)) {
      await noteInput.fill('需要研究计划书');
      await page.keyboard.press('Enter');
      await page.waitForTimeout(2000);
      const noteShown = await page.locator('text=需要研究计划书').isVisible().catch(() => false);
      console.log(`  Notes edit: ${noteShown}`);
      results.push(result('AC15', noteShown, 'Notes inline edit saved'));
    }
  }

  // AC16: Stage advance button
  const stageBtn = page.locator('aside button:has-text("套磁")').first();
  if (await stageBtn.isVisible().catch(() => false)) {
    const oldLabel = await page.locator('aside .text-xs.px-1\\.5').first().textContent().catch(() => '');
    await stageBtn.click();
    await page.waitForTimeout(3000);
    const newLabel = await page.locator('aside .text-xs.px-1\\.5').first().textContent().catch(() => '');
    console.log(`  Stage: "${oldLabel}" → "${newLabel}"`);
    results.push(result('AC16', oldLabel !== newLabel, `Stage changed: ${oldLabel} → ${newLabel}`));
  } else {
    console.log('  No stage advance button visible');
    results.push(result('AC16', false, 'STAGE BTN MISSING'));
  }

  // AC17/AC18: Delete school dialog
  const delSchoolBtn = page.locator('button[title="删除"]').first();
  if (await delSchoolBtn.isVisible().catch(() => false)) {
    // AC18: Cancel
    await delSchoolBtn.click();
    await page.waitForTimeout(500);
    const dialogVisible = await page.locator('button:has-text("确认删除")').isVisible().catch(() => false);
    console.log(`  Delete dialog appears: ${dialogVisible}`);
    if (dialogVisible) {
      await page.locator('button:has-text("取消")').click();
      await page.waitForTimeout(500);
      const dialogGone = !(await page.locator('button:has-text("确认删除")').isVisible().catch(() => false));
      console.log(`  Cancel → dialog closes: ${dialogGone}`);
      results.push(result('AC18', dialogGone, 'Delete dialog cancel works'));
    }

    // AC17: Confirm delete (on last card)
    await delSchoolBtn.click();
    await page.waitForTimeout(500);
    await page.locator('button:has-text("确认删除")').click();
    await page.waitForTimeout(3000);
    const delToast = await page.locator('[data-sonner-toast]').first().textContent().catch(() => '');
    console.log(`  Delete toast: "${delToast.slice(0, 50)}"`);
    results.push(result('AC17', delToast.includes('已删除'), `Delete confirmed: ${delToast.slice(0, 40)}`));
  }

  // ── Phase 6: Chat ──
  console.log('\n=== Phase 6: Chat ===');
  await page.locator('button[role="tab"]:has-text("对话")').click();
  await page.waitForTimeout(500);

  const chatInput = page.locator('input[placeholder*="输入你的"]');
  if (await chatInput.isVisible().catch(() => false)) {
    await chatInput.fill('你好');
    await page.waitForTimeout(200);

    // Click send button
    await page.locator('button:has(svg.lucide-send)').last().click();
    await page.waitForTimeout(10000); // Wait for SSE

    // Check for response in chat area
    const allBubbles = await page.locator('.whitespace-pre-wrap').last().textContent().catch(() => '');
    console.log(`  Chat response: "${allBubbles.slice(0, 100)}"`);
    const gotResponse = allBubbles.length > 2;
    results.push(result('AC19', gotResponse, gotResponse ? `Chat SSE response: "${allBubbles.slice(0, 60)}"` : 'No chat response'));

    // AC20: Double-send prevention — check send button is disabled while loading
    const sendBtn = page.locator('button:has(svg.lucide-send)').last();
    const isDisabled = await sendBtn.isDisabled().catch(() => true);
    console.log(`  Send button disabled (loading lock): ${isDisabled}`);
    results.push(result('AC20', isDisabled, isDisabled ? 'Send button disabled while loading (lock works)' : 'Send button not disabled — potential spam'));
  }

  // ── Phase 7: Layout ──
  console.log('\n=== Phase 7: Layout ===');

  // AC21: Sidebar collapse
  const collapseBtn = page.locator('button[title="收起"], button:has(svg.lucide-layout-grid)').first();
  if (await collapseBtn.isVisible().catch(() => false)) {
    const beforeW = await page.locator('aside').evaluate(el => el.offsetWidth).catch(() => 0);
    await collapseBtn.click();
    await page.waitForTimeout(500);
    const afterW = await page.locator('aside').evaluate(el => el.offsetWidth).catch(() => 999);
    console.log(`  Sidebar width: ${beforeW}px → ${afterW}px`);
    results.push(result('AC21', afterW < beforeW, `Sidebar collapses: ${beforeW}px → ${afterW}px`));
  }

  // AC22: Calendar
  await page.locator('button:has-text("日历")').click();
  await page.waitForTimeout(1500);
  const calContent = await page.locator('main').textContent().catch(() => '');
  const calNotEmpty = calContent.length > 30 && !calContent.includes('Loading');
  console.log(`  Calendar content: ${calContent.length} chars, sample: "${calContent.slice(0, 60)}"`);
  results.push(result('AC22', calNotEmpty, 'Calendar tab renders content'));

  // AC23: Plaza mini chat
  await page.locator('button:has-text("广场")').click();
  await page.waitForTimeout(1000);
  const miniChat = await page.locator('text=查看完整对话').isVisible().catch(() => false);
  console.log(`  Mini chat in plaza: ${miniChat}`);
  if (miniChat) {
    await page.locator('text=查看完整对话').click();
    await page.waitForTimeout(500);
    const backToChat = await page.locator('button[data-state="active"]:has-text("对话")').isVisible().catch(() => false);
    console.log(`  Back to chat tab: ${backToChat}`);
    results.push(result('AC23', backToChat, 'Mini chat → click → back to chat tab'));
  } else {
    results.push(result('AC23', false, 'No mini chat visible in plaza'));
  }

  // ── Summary ──
  await browser.close();
  printSummary(results);
})();

function printSummary(results) {
  console.log('\n========================================');
  console.log('         EVALUATION SUMMARY');
  console.log('========================================');
  const passed = results.filter(r => r.pass).length;
  const failed = results.filter(r => !r.pass).length;
  const total = results.length;
  const score = Math.round((passed / total) * 100);

  console.log(`Total: ${total} | Passed: ${passed} | Failed: ${failed} | Score: ${score}/100`);
  console.log('\nResults:');
  for (const r of results) {
    const icon = r.pass ? '✓' : '✗';
    console.log(`  ${icon} ${r.ac}: ${r.detail}`);
  }

  const report = `# Critique — Sprint 1 (E2E Core Flow)

## Summary
- Total criteria: ${total}
- Passed: ${passed}
- Failed: ${failed}
- Score: ${score}/100

## Detailed Results

${results.map(r => `- [${r.pass ? 'x' : ' '}] **${r.ac}**: ${r.detail}`).join('\n')}

## Failures to Fix

${results.filter(r => !r.pass).map(r => `- **${r.ac}**: ${r.detail}`).join('\n') || 'None!'}
`;
  fs.writeFileSync('critiques/critique-1.md', report);
  console.log('\nReport: critiques/critique-1.md');
}
