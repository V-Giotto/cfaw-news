// Isolated local UI smoke. Requires existing Playwright and Edge; installs nothing.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(require.resolve('playwright', { paths: [process.argv[2] || process.cwd()] }));
const root = path.resolve(__dirname, '..');
const out = path.join(root, '.local/g0/2026-10-20');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      return url.hostname === '127.0.0.1' && url.port === '8123' ? route.continue() : route.abort();
    });
    const response = await page.goto('http://127.0.0.1:8123/');
    assert.equal(response.status(), 200);
    const article = page.getByRole('button', { name: '阅读：G0 audit synthetic AI release', exact: true });
    await article.waitFor();
    assert.equal(await article.count(), 1);
    await page.getByRole('button', { name: '查看来源状态', exact: true }).click();
    await page.getByText('来源超时、不可用或无法解析；已保留此前资料。', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(out, 'source-failure.png'), fullPage: true });
    await article.click();
    await page.getByText('原文读取未开启，可打开原始来源。', { exact: true }).waitFor();
    await page.getByRole('region', { name: '新闻阅读', exact: true })
      .getByRole('heading', { name: 'G0 audit synthetic AI release', exact: true }).waitFor();
    await page.getByRole('button', { name: '关闭阅读', exact: true }).click();
    await page.getByRole('button', { name: '我的关注', exact: true }).click();
    await page.getByText('从目标出发，让消息变成线索。', { exact: true }).waitFor();
    await page.getByRole('button', { name: '行动日程', exact: true }).click();
    await page.getByRole('heading', { name: '给下一步，留一点时间。', exact: true }).waitFor();
    await page.getByRole('button', { name: '检查记录', exact: true }).click();
    await page.getByRole('heading', { name: '每一次判断，都有迹可循。', exact: true }).waitFor();
    assert.deepEqual(errors, []);
    const result = { status: 'passed', browser: 'existing Microsoft Edge, headless Playwright',
      viewport: '1440x1000', record_origin: 'synthetic', production_database_used: false,
      checks: ['HTTP 200 and synthetic article visible without Goal', 'source failure and cached article coexist',
        'reader opens and disabled fetch is explicit', 'Goal/calendar/history navigation remains accessible'],
      console_errors: errors, screenshot: '.local/g0/2026-10-20/source-failure.png', live_model_called: false };
    fs.writeFileSync(path.join(out, 'browser.json'), JSON.stringify(result, null, 2) + '\n');
    process.stdout.write(JSON.stringify(result) + '\n');
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(String(error.stack) + '\n'); process.exitCode = 1; });
