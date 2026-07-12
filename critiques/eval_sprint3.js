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
  R('login', loggedIn, loggedIn ? 'OK' : 'FAIL');
  if (!loggedIn) { await browser.close(); return summarize(); }

  async function ask(q) {
    const input = page.locator('input[placeholder*="输入你的"]');
    await input.fill(q);
    await page.locator('button:has(svg.lucide-send)').last().click();
    await page.waitForTimeout(25000); // wait for SSE + web search + LLM
    // Get all chat bubbles — assistants are on the left (no flex-row-reverse)
    const bubbles = await page.locator('.flex.gap-3').allTextContents().catch(() => []);
    // Filter out user messages (short, match the query) and get assistant ones
    const assistantMsgs = bubbles.filter(b => b.length > q.length + 3);
    const last = assistantMsgs[assistantMsgs.length - 1] || '';
    return last;
  }

  // C1: RAG knowledge base query
  console.log('\n=== C1: RAG query ===');
  const c1 = await ask('出愿需要什么材料');
  const c1ok = c1.length > 10 && !c1.includes('未找到') && !c1.includes('抱歉');
  R('C1-rag', c1ok, `Response (${c1.length} chars): "${c1.slice(0, 80)}"`);

  // C2: Web search fallback
  console.log('\n=== C2: Web fallback ===');
  const c2 = await ask('京都大学情报科托福要多少分');
  const c2ok = c2.length > 10 && !c2.includes('未找到') && !c2.includes('抱歉');
  R('C2-web', c2ok, `Response (${c2.length} chars): "${c2.slice(0, 80)}"`);

  // C3: Greeting fast path
  console.log('\n=== C3: Greeting ===');
  const c3 = await ask('你好');
  const c3ok = c3.length > 2;
  R('C3-greet', c3ok, `Response: "${c3.slice(0, 60)}"`);

  // C4: Verify no errors
  console.log('\n=== C4: No errors ===');
  const allMsgs = await page.locator('.whitespace-pre-wrap').allTextContents().catch(() => []);
  const noErrors = !allMsgs.some(m => m.includes('[错误]') || m.includes('Error:'));
  R('C4-noerror', noErrors, `Error messages found: ${!noErrors}`);

  await browser.close();
  summarize();
})();

function summarize() {
  const p = results.filter(r => r.pass).length;
  const f = results.filter(r => !r.pass).length;
  console.log(`\n===== SCORE: ${Math.round(p/(p+f)*100)}/100 (${p}/${p+f}) =====`);
}
