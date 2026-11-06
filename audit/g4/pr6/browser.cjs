// PR6 QA only: actual isolated API + licensed offline material; time fixtures are separate.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(require.resolve('playwright', { paths: [process.argv[2]] }));
const root = path.resolve(__dirname, '../../..');
assert(process.env.CFAW_PR6_RUN && process.env.CFAW_PR6_URL && process.env.CFAW_PR6_PILOT, 'explicit QA targets required');
const run = path.resolve(process.env.CFAW_PR6_RUN);
const base = process.env.CFAW_PR6_URL;
const pilot = JSON.parse(fs.readFileSync(path.join(run, process.env.CFAW_PR6_PILOT, 'result.json'), 'utf8'));
const fixtures = JSON.parse(fs.readFileSync(path.join(run, 'browser-contracts-native/fixtures.json'), 'utf8'));
const out = path.join(run, 'browser-pilot'); fs.mkdirSync(out, { recursive: true });
const checks = []; const external = []; const errors = []; const writes = [];
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function fresh(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN', timezoneId: 'Asia/Shanghai' });
  await context.addInitScript(() => {
    window.__qaNotifications = 0;
    window.Notification = Object.assign(function () { window.__qaNotifications++; throw new Error('notifications forbidden'); }, {
      requestPermission: () => { window.__qaNotifications++; return Promise.resolve('denied'); }, permission: 'denied' });
  });
  const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== base) { external.push(url.origin + url.pathname); return route.abort(); }
    if (route.request().method() === 'POST') writes.push({ path: url.pathname, body: route.request().postDataJSON() });
    return route.continue();
  });
  return { context, page };
}
async function read(page, url) { const response = await page.request.get(base + '/api' + url); assert.equal(response.status(), 200); return response.json(); }

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const { context, page } = await fresh(browser);
    await page.goto(base); await page.getByRole('heading', { name: '我的情报', exact: true }).waitFor();
    await page.getByText(/raw_news_only/).first().waitFor();
    assert.equal(await page.locator('.briefing-card').count(), 0);
    await page.getByText(/source gaps/).first().waitFor();
    await page.screenshot({ path: path.join(out, 'licensed-raw-home.png'), fullPage: true });
    checks.push('actual persisted real-origin MIT material: honest raw_news_only, empty Focus/Radar, Archive and gaps');

    await page.locator('.briefing-archive article').first().getByRole('button').click();
    await page.getByRole('heading', { name: '来源与许可元数据', exact: true }).waitFor();
    const quotes = page.getByRole('button', { name: '阅读此历史引用', exact: true });
    if (await quotes.count()) {
      await quotes.first().click(); await page.getByRole('region', { name: '核对本轮证据', exact: true }).waitFor();
      await page.keyboard.press('Escape');
    } else {
      await page.getByText(/hold \/ 许可受限/).waitFor();
      assert.equal(await page.locator('dialog .briefing-claim').count(), 0);
    }
    for (const name of ['撤销已了解', '撤销不感兴趣']) {
      const existing = page.getByRole('button', { name, exact: true });
      if (await existing.count()) await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/intelligence/interactions') && r.request().method() === 'POST'), existing.click()]);
    }
    const beforeFeedback = new Set((await read(page, '/intelligence/interactions?limit=500')).map(row => row.id));
    await page.getByRole('button', { name: '标记已了解', exact: true }).click();
    await page.getByRole('button', { name: '撤销已了解', exact: true }).click();
    await page.getByRole('button', { name: '暂不感兴趣', exact: true }).click();
    await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/intelligence/interactions') && r.request().method() === 'POST'), page.getByRole('button', { name: '撤销不感兴趣', exact: true }).click()]);
    await page.getByRole('button', { name: '撤销不感兴趣', exact: true }).waitFor({ state: 'detached' });
    await page.getByRole('button', { name: '关闭详情', exact: true }).click();
    const observations = await read(page, '/intelligence/interactions?limit=500');
    for (const kind of ['opened', 'ack', 'dismiss', 'retract']) assert.ok(observations.some(row => row.kind === kind));
    assert.equal(observations.filter(row => row.kind === 'retract' && !beforeFeedback.has(row.id)).length, 2);
    assert.equal(observations.filter(row => row.kind === 'rendered').length, 0);
    assert.ok(observations.every(row => row.learned === false));
    checks.push('actual SQLite: hold metadata, opened/ack/dismiss/two retracts; no fabricated rendered or claim promotion for raw Archive');

    await page.getByRole('button', { name: '生成简报', exact: true }).click();
    await page.getByText(/任务状态：completed/).waitFor();
    const refreshed = await read(page, '/intelligence/briefings/latest'); assert.notEqual(refreshed.id, pilot.briefing_id);
    await page.getByRole('button', { name: '生成简报', exact: true }).click();
    await page.getByRole('button', { name: '取消生成', exact: true }).click();
    await page.getByText(/取消请求已确认/).waitFor(); await pause(2500);
    assert.equal((await read(page, '/intelligence/briefings/latest')).id, refreshed.id);
    checks.push('actual native refresh and cancellation with bounded QA entry delay; no late replacement of last snapshot');
    await page.getByRole('textbox', { name: '历史快照 ID' }).fill(pilot.briefing_id);
    await page.getByRole('button', { name: '打开历史快照', exact: true }).click();
    await page.getByText(new RegExp('正在查看历史快照 ' + pilot.briefing_id)).waitFor();
    await page.getByRole('button', { name: '返回最新简报', exact: true }).click();
    checks.push('actual old snapshot access preserves immutable source and latest pointer');

    for (const budget of ['180', '900', '420']) {
      await page.getByRole('combobox', { name: '估算阅读预算' }).selectOption(budget);
      await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/intelligence/persona') && r.request().method() === 'POST'),
        page.getByRole('button', { name: '保存预算', exact: true }).click()]);
      await page.getByText(/偏好已保存/).waitFor();
      await page.waitForFunction(() => [...document.querySelectorAll('button')].find(b => b.textContent === '重新读取')?.disabled === false);
      assert.equal((await read(page, '/intelligence/persona')).attention_budget_seconds, Number(budget));
    }
    checks.push('actual versioned Persona budgets 180/900/420; historical snapshot budget remains uncomputed');
    await page.getByRole('button', { name: '资讯资料库', exact: true }).click();
    await page.getByRole('button', { name: '阅读：Vite 8.3.4 packaged README · MIT', exact: true }).click();
    await page.getByRole('region', { name: '新闻阅读', exact: true }).waitFor();
    await page.getByText(/A dev server that provides/).first().waitFor();
    await page.getByRole('button', { name: '关闭阅读', exact: true }).click();

    await page.getByRole('button', { name: '添加关注目标', exact: true }).click();
    const form = page.getByRole('dialog');
    await form.getByLabel('关注名称', { exact: true }).fill('PR6 Vite 工具核实');
    await form.getByLabel('我想做什么', { exact: true }).fill('核实 Vite build 和 HMR 的资料与适用条件');
    await form.getByLabel('检索关键词', { exact: true }).fill('Vite,HMR,Rolldown');
    await form.getByRole('checkbox').check();
    await form.getByRole('button', { name: '确认并保存关注', exact: true }).click();
    await page.getByRole('button', { name: '检查本轮证据', exact: true }).click();
    await page.getByRole('heading', { name: '本轮判断', exact: true }).waitFor();
    const runs = await read(page, '/runs'); assert.equal(runs[0].status, 'completed'); assert.equal(runs[0].metrics.model_called, false);
    await page.getByRole('button', { name: '继续观察', exact: true }).click();
    await page.getByRole('button', { name: '预览并确认', exact: true }).click();
    await page.getByRole('button', { name: '确认并导入日程', exact: true }).click();
    await page.getByText(/已保存到行动日程/).waitFor();
    const approval = writes.find(row => /\/approve$/.test(row.path)); assert.ok(approval);
    const repeated = await page.request.post(base + approval.path, { data: approval.body });
    assert.equal((await repeated.json()).created, false);
    assert.equal((await read(page, '/schedules')).length, 1);
    assert.equal((await read(page, '/runs/' + runs[0].id)).decision.choice, 'watch');
    await page.getByRole('button', { name: '行动日程', exact: true }).click();
    await page.getByRole('button', { name: '标记完成', exact: true }).click();
    await page.getByRole('button', { name: '已完成', exact: true }).click();
    await page.getByText('核实资料与个人适用条件', { exact: true }).waitFor();
    await page.getByRole('button', { name: '检查记录', exact: true }).click();
    await page.getByRole('table', { name: '检查记录', exact: true }).getByRole('button', { name: /PR6 Vite 工具核实/ }).click();
    await page.getByRole('heading', { name: '本轮判断', exact: true }).waitFor();
    checks.push('actual legacy Goal→Run→Decision→explicit Schedule→idempotent retry→completion→history reopen');
    assert.equal(await page.evaluate(() => window.__qaNotifications), 0);
    assert.equal(writes.filter(row => row.path.includes('/sources/') || row.path.includes('subscribe')).length, 0);
    checks.push('no Notification invocation, automatic subscription, source fetch or external third-party operation');
    await page.screenshot({ path: path.join(out, 'legacy-workflow.png'), fullPage: true }); await context.close();

    for (const days of [1, 3, 7]) {
      const { context, page } = await fresh(browser);
      const data = structuredClone(fixtures.real_raw);
      const end = '2026-01-08T00:00:00Z', start = new Date(Date.parse(end) - days * 86400000).toISOString();
      const previous = structuredClone(data.briefing); previous.id = 'last-visit'; previous.as_of = start; previous.generated_at = start;
      previous.archive[0].event_revision = 'old-revision';
      data.briefing.as_of = end; data.briefing.generated_at = end;
      const coverage = data.briefing.coverage; coverage.requested_start_at = start; coverage.requested_end_at = end;
      coverage.has_gap = true; coverage.effective_statuses = ['service_offline'];
      coverage.windows = [{ coverage_window_id: 'qa-offline', source_id: 'official', start_at: start, end_at: end, observed_at: end, status: 'service_offline', reason: 'authored QA time-window fixture' }];
      coverage.window_count = 1; coverage.status_counts = { service_offline: 1 }; coverage.missing_source_ids = []; coverage.unobserved_source_ids = [];
      coverage.sources[0] = { source_id: 'official', status: 'service_offline', observed_statuses: ['service_offline'], window_refs: ['/history_input/replay/source_coverage/0'],
        segments: [{ start_at: start, end_at: end, status: 'service_offline', observed_statuses: ['service_offline'], window_refs: ['/history_input/replay/source_coverage/0'], reason_codes: ['offline_qa_window'] }],
        confirmed_intervals: [], unconfirmed_intervals: [{ start_at: start, end_at: end }], unobserved_intervals: [] };
      const prior = { ...fixtures.synthetic.interactions[0], kind: 'opened', source: 'client_confirmation', briefing_id: 'last-visit', sequence: 1, available_at: start };
      await page.route('**/api/**', route => {
        const p = new URL(route.request().url()).pathname.slice(4);
        const result = p === '/intelligence/status' ? data.status : p === '/intelligence/persona' ? data.persona
          : p === '/intelligence/briefings/latest' ? data.briefing : p === '/intelligence/briefings/last-visit' ? previous
            : p === '/intelligence/interactions' ? [prior] : p === '/config' ? { mode: 'baseline', counts: { goals: 0, runs: 0, articles: 0 } } : [];
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify(result) });
      });
      await page.goto(base); await page.getByText(/修订变化 1/).waitFor();
      await page.getByText(/上次可观察访问/).waitFor(); await page.getByText(/source gaps/).first().waitFor();
      await page.getByText(/打开不等于知道/).first().waitFor();
      await page.evaluate(() => { const label = document.createElement('p'); label.textContent = 'PR6 authored time-window fixture, not live news'; document.body.prepend(label); });
      await page.screenshot({ path: path.join(out, `revisit-${days}d-ui-fixture.png`), fullPage: true });
      checks.push(`${days}-day UI fixture: last observable visit, revision delta and offline gap; not actual wall-clock wait or native feedback ranking`);
      await context.close();
    }
    assert.deepEqual(external, []); assert.deepEqual(errors, []);
    const result = { status: 'PASS', browser_version: browser.version(), checks, external_attempts: external, page_errors: errors,
      record_origin: 'real MIT pilot + separately labelled authored UI time fixtures', production_database_used: false,
      live_network_smoke: 'not_evaluated', late_persona_history: 'not fixed; existing PR3 limitation',
      qa_delay_seconds: 2, screenshots: fs.readdirSync(out).filter(name => name.endsWith('.png')) };
    fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify(result, null, 2)); process.stdout.write(JSON.stringify(result, null, 2));
  } finally { await browser.close(); }
})().catch(error => { fs.writeFileSync(path.join(out, 'failure.txt'), String(error.stack)); process.stderr.write(String(error.stack)); process.exitCode = 1; });
