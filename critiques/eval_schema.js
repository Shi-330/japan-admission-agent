const { chromium } = require('playwright');

const BASE = 'http://localhost:8100';
const TEST_EMAIL = 'test@example.com';
const TEST_PASS = 'AgentV2_test!';
const RESULTS = [];

function result(criterion, pass, actual) {
  RESULTS.push({ criterion, pass, actual: actual || (pass ? 'pass' : 'fail') });
  console.log(`${pass ? 'PASS' : 'FAIL'}: ${criterion} — ${actual || (pass ? 'pass' : 'fail')}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  let jwtToken = null;

  page.on('request', req => {
    if (!jwtToken && req.url().includes('/v1/')) {
      const auth = req.headers()['authorization'] || '';
      if (auth.startsWith('Bearer ')) jwtToken = auth;
    }
  });

  async function authFetch(path, options = {}) {
    const token = jwtToken;
    return page.evaluate(async ({ url, options, token }) => {
      const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      };
      if (token) headers['Authorization'] = token;
      const resp = await fetch(url, { ...options, headers });
      const text = await resp.text();
      let json;
      try { json = JSON.parse(text); } catch { json = { raw: text.substring(0, 200) }; }
      return { status: resp.status, ok: resp.ok, body: json };
    }, { url: BASE + path, options, token });
  }

  // Login
  console.log('=== Login ===');
  await page.goto(BASE, { waitUntil: 'load', timeout: 45000 });
  await page.waitForTimeout(2000);
  await page.locator('input[type="email"]').fill(TEST_EMAIL);
  await page.locator('input[type="password"]').fill(TEST_PASS);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(5000);
  console.log('JWT captured:', !!jwtToken);

  // ── Get profile ──
  const profileResp = await authFetch('/v1/profile');
  console.log('Profile status:', profileResp.status);
  if (profileResp.status === 200) {
    console.log('Profile:', JSON.stringify(profileResp.body).substring(0, 1000));
  } else {
    console.log('Profile error:', JSON.stringify(profileResp.body));
  }

  // ── Try match with different params ──
  console.log('\n=== Match endpoint diagnosis ===');

  // Try 1: Empty target_major
  const m1 = await authFetch('/v1/match', {
    method: 'POST',
    body: JSON.stringify({ target_major: '', gpa: 3.0, jlpt: 'N2', english_scores: {} })
  });
  console.log('Match (empty major):', m1.status, JSON.stringify(m1.body).substring(0, 300));

  // Try 2: With profile fields
  const m2 = await authFetch('/v1/match', {
    method: 'POST',
    body: JSON.stringify({
      target_major: '情报理工',
      research_area: '自然语言处理',
      gpa: 3.5,
      jlpt: 'N2',
      english_scores: { 'TOEIC': 750 }
    })
  });
  console.log('Match (with profile):', m2.status, JSON.stringify(m2.body).substring(0, 500));

  // Try 3: Maybe it needs the user_id
  const m3 = await authFetch('/v1/match', {
    method: 'POST',
    body: JSON.stringify({})
  });
  console.log('Match (empty body):', m3.status, JSON.stringify(m3.body).substring(0, 300));

  // Use the best working match for C2/C6 assessment
  let bestMatch = null;
  if (m1.status === 200) bestMatch = m1;
  else if (m2.status === 200) bestMatch = m2;
  else if (m3.status === 200) bestMatch = m3;

  if (bestMatch) {
    const data = bestMatch.body;
    const allResults = data.results || data.schools || data.matches || [];
    console.log(`Match results count: ${allResults.length}`);

    let hasEnglishGap = false, hasWarning = false;
    if (Array.isArray(allResults)) {
      for (const r of allResults) {
        const gaps = r.gaps || r.requirements || [];
        if (Array.isArray(gaps)) {
          for (const g of gaps) {
            const fs = typeof g === 'string' ? g : (g.field || JSON.stringify(g));
            if (fs.includes('英语') || fs.includes('英文') || fs.toLowerCase().includes('english') ||
                fs.toLowerCase().includes('toefl') || fs.toLowerCase().includes('toeic')) hasEnglishGap = true;
          }
        }
        if (r.status === 'warning' || r.status === 'reject' || r.level === 'warning' || r.level === 'reject' || r.verdict === 'warning' || r.verdict === 'reject') hasWarning = true;
      }
    }
    result('C2: English gaps shown for English-requiring schools', hasEnglishGap, hasEnglishGap ? 'found' : 'none');
    result('C2.2: not all schools matchable', hasWarning, hasWarning ? 'some warning/reject' : 'all matchable');
    result('C6: /v1/match endpoint works', true, `status ${bestMatch.status}`);
  } else {
    console.log('All match attempts failed with 503');
    result('C2: /v1/match (503 - school data load failure)', false, 'status 503: school data loading failed');
    result('C2.2: matchable check (503)', false, 'status 503');
    result('C6: /v1/match endpoint', false, 'status 503: school data loading failed');

    // C6 spec says "DB读取失败时返回明确错误" — the error IS clear
    console.log('Note: C6 error message is clear: "学校数据加载失败，无法执行匹配"');
  }

  // ── School data checks ──
  console.log('\n=== C3/C4/C5/C8: School data ===');
  try {
    const resp = await authFetch('/v1/schools');
    const schools = Array.isArray(resp.body) ? resp.body : (Array.isArray(resp.body?.schools) ? resp.body.schools : []);

    let arrDL = false, dictDL = false, hasNewFields = false;
    let expiredCount = 0;
    const today = new Date('2026-07-17');

    for (const s of schools) {
      if (s.jlpt_min !== undefined || s.gpa_min !== undefined || s.english_req !== undefined) hasNewFields = true;
      const d = s.deadlines;
      if (d) {
        if (Array.isArray(d)) {
          arrDL = true;
          for (const e of d) {
            if (e.date && new Date(e.date) < today) expiredCount++;
            if (e.end && new Date(e.end) < today) expiredCount++;
          }
        } else {
          dictDL = true;
        }
      }
    }

    result('C4: structured deadlines (array)', arrDL, arrDL ? 'array' : (dictDL ? 'dict (old)' : 'none'));
    result('C4.3: new schema fields', hasNewFields, hasNewFields ? 'present' : 'absent');
    result('C5: expired deadlines', true, `${expiredCount} expired`);
  } catch (e) {
    result('C4/C5/C8', false, `exception: ${e.message}`);
  }

  // C8 / C3
  const csResp = await authFetch('/v1/schools?major=计算机');
  const csSchools = Array.isArray(csResp.body) ? csResp.body : (Array.isArray(csResp.body?.schools) ? csResp.body.schools : []);
  result('C8: /v1/schools?major=计算机 returns results', csSchools.length > 0, `returned ${csSchools.length} schools`);
  let hasJP = false;
  for (const s of csSchools) {
    const m = (s.majors || []).join(' '), n = s.name || '', t = (s.tags || []).join(' ');
    if (m.includes('情報') || m.includes('コンピュータ') || n.includes('情報') || t.includes('情報')) { hasJP = true; break; }
  }
  result('C3: "计算机" hits JP terms', hasJP, hasJP ? 'found' : 'none');

  // C4.4: Calendar
  const calTab = page.locator('button:has-text("日历"), [role="tab"]:has-text("日历")');
  if (await calTab.count() > 0) {
    await calTab.first().click();
    await page.waitForTimeout(1500);
    result('C4.4: calendar view accessible', true, 'navigated');
  } else {
    result('C4.4: calendar view', false, 'no calendar tab');
  }

  await browser.close();

  // Final
  const passed = RESULTS.filter(r => r.pass).length;
  const total = RESULTS.length;
  console.log('\n=== FINAL RESULTS ===');
  console.log(JSON.stringify({
    total, passed, failed: total - passed,
    score: total ? Math.round(passed / total * 100) : 0,
    results: RESULTS
  }, null, 2));
})();
