const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  await page.goto('http://localhost:8000', { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(1000);

  // 1. 检查登录页
  console.log('=== 1. 登录页 ===');
  const loginTab = page.locator('button:has-text("登录")').first();
  const registerTab = page.locator('button:has-text("注册")').first();
  console.log('登录tab:', await loginTab.isVisible().catch(() => false));
  console.log('注册tab:', await registerTab.isVisible().catch(() => false));
  console.log('邮箱输入框:', await page.locator('input[type="email"]').isVisible().catch(() => false));
  console.log('密码输入框:', await page.locator('input[type="password"]').isVisible().catch(() => false));
  console.log('提交按钮:', await page.locator('button[type="submit"]').textContent().catch(() => 'NOT FOUND'));

  // 2. 检查忘记密码
  console.log('\n=== 2. 忘记密码 ===');
  const forgotLink = page.locator('text=忘记密码');
  console.log('忘记密码链接:', await forgotLink.isVisible().catch(() => false));

  if (await forgotLink.isVisible().catch(() => false)) {
    await forgotLink.click();
    await page.waitForTimeout(300);
    console.log('密码输入消失:', !(await page.locator('input[type="password"]').isVisible().catch(() => true)));
    console.log('按钮变发送重置:', await page.locator('button[type="submit"]').textContent().catch(() => ''));
    console.log('返回登录:', await page.locator('text=返回登录').isVisible().catch(() => false));

    // 空邮箱点发送
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(1000);
    const toastText1 = await page.locator('[data-sonner-toast]').first().textContent().catch(() => '');
    console.log('空邮箱 toast:', toastText1.slice(0, 50));

    // 点返回登录
    await page.locator('text=返回登录').click();
    await page.waitForTimeout(200);
  }

  // 3. 检查注册
  console.log('\n=== 3. 注册 ===');
  await registerTab.first().click();
  await page.waitForTimeout(200);
  console.log('按钮文字:', await page.locator('button[type="submit"]').textContent().catch(() => ''));
  console.log('忘记密码隐藏:', !(await page.locator('text=忘记密码').isVisible().catch(() => true)));

  // 空值提交注册
  await page.fill('input[type="email"]', '');
  await page.fill('input[type="password"]', '');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(1500);

  // 浏览器原生校验会拦截空值，看是否有toast或页面反应
  const stillOnPage = await page.locator('input[type="email"]').isVisible().catch(() => false);
  console.log('空值提交后仍在注册页:', stillOnPage);

  // 填假邮箱注册
  await page.fill('input[type="email"]', 'test_reg_' + Date.now() + '@example.com');
  await page.fill('input[type="password"]', 'test123456');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(4000);

  const toastText2 = await page.locator('[data-sonner-toast]').first().textContent().catch(() => '');
  console.log('注册toast:', toastText2.slice(0, 80));

  // 检查按钮loading态出现过
  console.log('仍在注册页:', await page.locator('input[type="email"]').isVisible().catch(() => false));
  console.log('当前按钮文字:', await page.locator('button[type="submit"]').textContent().catch(() => ''));

  // 4. 切回登录试错误密码
  console.log('\n=== 4. 错误密码登录 ===');
  await loginTab.first().click();
  await page.waitForTimeout(200);
  await page.fill('input[type="email"]', 'test@example.com');
  await page.fill('input[type="password"]', 'wrongpassword');
  await page.locator('button[type="submit"]').click();
  await page.waitForTimeout(4000);

  const toastText3 = await page.locator('[data-sonner-toast]').first().textContent().catch(() => '');
  console.log('错误密码toast:', toastText3.slice(0, 80));

  await browser.close();
  console.log('\n=== DONE ===');
})();
