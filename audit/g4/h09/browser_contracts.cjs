// PR5 browser engineering checks. All mocked stories are authored fixtures, never live news.
// Run the isolated server from browser_fixture.py first. No package install or external requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(require.resolve('playwright', { paths: [process.argv[2] || process.cwd()] }));
const root = path.resolve(__dirname, '../../..');
assert(process.env.CFAW_PR5_OUT && process.env.CFAW_PR5_URL && process.env.CFAW_QA_BOUNDARY_URL, 'explicit QA targets required');
const out = path.resolve(root, process.env.CFAW_PR5_OUT);
const base = process.env.CFAW_PR5_URL;
const fixtures = JSON.parse(fs.readFileSync(path.join(out, 'fixtures.json'), 'utf8'));
const clone = v => structuredClone(v);
const pause = ms => new Promise(r => setTimeout(r, ms));
const checks = [];
const errors = [];
const assetErrors = [];
function checkAssets(page) {
  page.on('response', response => { const url = new URL(response.url());
    if (url.origin === new URL(base).origin && !url.pathname.startsWith('/api/') && response.status() >= 400)
      assetErrors.push({ path: url.pathname, status: response.status() });
  });
}
const knownArticle = { id: 'legacy-mock', title: 'PR5 authored legacy article', original_title: 'PR5 authored legacy article',
  source: 'Authored fixture', source_url: 'https://example.test/mock', summary: 'Isolated compatibility fixture.',
  published_at: '2026-01-01T00:00:00Z', captured_at: '2026-01-01T00:00:00Z', origin: 'feed', coverage_note: 'Engineering mock', source_role: 'official',
  content_hash: 'a'.repeat(64), paragraphs: [{ id: 'p1', text: 'Legacy snapshot body', kind: 'rss_body' }], source_id: 'official', image_status: 'no_image' };

// Simulates a future qualified real-shaped HTTP response ONLY inside this harness.
// This cannot make the PR4 server qualify real Focus/Radar, which it still rejects.
function realFixture(source) {
  const convert = (v, key) => Array.isArray(v) ? v.map(x => convert(x, key)) : v && typeof v === 'object'
    ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, convert(x, k)]))
    : v === 'synthetic_text' ? 'publisher_text' : v === 'synthetic_development' ? 'real' : v === 'synthetic' ? (['rights', 'redistribution_rights'].includes(key) ? 'permitted' : 'real') : v;
  return convert(clone(source));
}
function authoredPlan(source = fixtures.synthetic) {
  const result = realFixture(source);
  result.briefing.mode = 'real';
  result.status.mode = 'real'; result.persona.record_origin = 'real';
  result.status.head.sequence = 10;
  result.interactions = [];
  const initial = result.briefing.archive[0];
  const initialDelivery = result.briefing.deliveries[0];
  assert.ok(initialDelivery, 'native synthetic fixture should contain one delivery');
  initial.native_tier = 'focus'; initial.evidence_status = 'attributed';
  initialDelivery.tier = 'focus'; initialDelivery.status = 'focus';
  result.detail.event = clone(initial); result.detail.candidate.rule_item.tier_candidate = 'focus';
  const item = result.detail.candidate.rule_item;
  item.what_happened = { ...item.headline, text: 'HTTP MOCK ONLY: Atlas changed a local capability.' };
  item.why_it_matters = { text: 'Conditional relevance for the authored test.', kind: 'inference', rule_id: 'conditional_same_scope_evaluation', premise_claim_keys: item.selected_claim_keys, limitations: ['Not independently verified.'] };
  result.detail.candidate.rule_item.uncertainties = ['工程 HTTP mock，非真实资讯'];
  const prefix = (initialDelivery.content_refs[0] || '/history_input/replay/candidates/0/rule_item/headline').split('/rule_item/')[0] + '/rule_item/';
  initialDelivery.projection = 'focus';
  initialDelivery.content_refs = [prefix + 'headline', ...item.claim_summaries.map((_, i) => prefix + 'claim_summaries/' + i),
    ...item.risks.map((_, i) => prefix + 'risks/' + i), prefix + 'uncertainties/0', prefix + 'what_happened', prefix + 'why_it_matters'];
  initialDelivery.omitted_refs = [];
  result.briefing.unmet_protected_event_keys = ['protected-mock-missed'];
  return result;
}

async function harness(browser, data, options = {}) {
  const context = await browser.newContext({ viewport: options.viewport || { width: 1440, height: 900 } });
  const page = await context.newPage();
  checkAssets(page);
  page.on('pageerror', e => errors.push(e.message));
  const state = { data: clone(data), requests: [], readingRequests: 0, malformed: false, lostAck: false, detailFail: false, permissionDenied: false, offline: false, conflict: false, slowAck: false, receipts: new Map() };
  const reply = (route, data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
  await page.route('**/*', async route => {
    const req = route.request(); const url = new URL(req.url());
    if (url.origin !== new URL(base).origin) return route.abort();
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const p = url.pathname.slice(4); const d = state.data;
    if (state.offline) return route.abort('internetdisconnected');
    if (req.method() === 'POST') {
      const body = req.postDataJSON(); state.requests.push({ p, body });
      if (state.conflict) return reply(route, { code: 'G4_SNAPSHOT_VERSION_CONFLICT', database_state: 'unchanged' }, 409);
      if (state.receipts.has(body.idempotency_key)) return reply(route, { ...state.receipts.get(body.idempotency_key), deduplicated: true }, 201);
      const id = 'mock-write-' + state.requests.length;
      const receipt = { resource_id: id, deduplicated: false, head: d.status.head };
      if (p === '/intelligence/persona') {
        d.persona.attention_budget_seconds = body.attention_budget_seconds; d.persona.version++;
      } else if (p === '/intelligence/briefings') {
        d.run = { id, version: 1, status: 'running', cancel_requested: false, created_at: d.briefing.generated_at,
          as_of: d.briefing.as_of, started_at: d.briefing.generated_at, finished_at: null, persona_version_id: d.persona.id, snapshot_id: null, reason_codes: [], input_sha256: 'a'.repeat(64) };
      } else if (p.endsWith('/cancel')) { d.run.status = 'cancelled'; d.run.version++; }
      else if (p === '/intelligence/interactions') {
        d.status.head.sequence++;
        d.interactions.push({ id, briefing_id: body.briefing_id, target_id: body.target_id, kind: body.kind,
          sequence: d.status.head.sequence, ordinal: 0, available_at: '2026-01-01T00:00:10Z', persona_version_id: d.persona.id,
          retracts_id: body.retracts_id || null, client_occurred_at: null, source: body.kind === 'rendered' || body.kind === 'opened' ? 'client_confirmation' : 'explicit_user', learned: false });
      }
      state.receipts.set(body.idempotency_key, receipt);
      if (state.slowAck && body.kind === 'ack') await pause(400);
      if (state.lostAck && body.kind === 'ack') { state.lostAck = false; return route.abort('failed'); }
      return reply(route, receipt, p === '/intelligence/briefings' ? 202 : 201);
    }
    if (p === '/intelligence/visits/latest') return reply(route, null);
    if (p === '/intelligence/briefings') return reply(route, { stream_id: d.status.head.stream_id, through_version: d.briefing.version,
      items: [d.briefing].map(b => ({ id:b.id,version:b.version,as_of:b.as_of,generated_at:b.generated_at,evidence_status:b.evidence_status })), next_before_version:null });
    if (p === '/intelligence/status') {
      if (state.permissionDenied) return reply(route, { code: 'G4_ORIGIN_FORBIDDEN', database_state: 'unchanged' }, 403);
      return reply(route, d.status);
    }
    if (p === '/intelligence/persona') return reply(route, d.persona);
    if (p.startsWith('/intelligence/briefings/')) {
      if (state.malformed) { const invalid = clone(d.briefing); delete invalid.coverage; return reply(route, invalid); }
      if (p.endsWith('/old-mock') && d.previous) return reply(route, d.previous);
      return reply(route, d.briefing);
    }
    if (p.startsWith('/intelligence/runs/')) return reply(route, d.run);
    if (p === '/intelligence/interactions') return reply(route, d.interactions.slice(Number(url.searchParams.get('offset') || 0), Number(url.searchParams.get('offset') || 0) + 500));
    if (p === '/intelligence/events/detail') {
      if (state.detailFail) return reply(route, { code: 'G4_SNAPSHOT_PAYLOAD_MISMATCH', database_state: 'unchanged' }, 503);
      const detail = clone(d.detail);
      if (url.searchParams.get('briefing_id') === 'old-mock' && d.previousDetail) return reply(route, d.previousDetail);
      return reply(route, detail);
    }
    if (p === '/goals') return reply(route, []);
    if (p === '/runs' || p === '/schedules') return reply(route, []);
    if (p === '/config') return reply(route, { version: 'PR5-mock', mode: 'baseline', model: null, news_auto_refresh: false, counts: { articles: 1, goals: 0, runs: 0 } });
    if (p === '/sources') return reply(route, [{ id: 'official', label: 'Authored fixture source', primary: true, enabled: true, kind: 'rss', category: 'ai', language: 'en', article_count: 1, state: { status: 'error' } }]);
    if (p === '/articles') return reply(route, [knownArticle]);
    if (p.includes('/reading')) { state.readingRequests++; return reply(route, { status: 'unavailable', nodes: [], text_chars: 0, error: 'PR5 isolated fetch disabled' }); }
    return reply(route, { code: 'G4_NOT_FOUND', database_state: 'unchanged' }, 404);
  });
  await page.goto(base);
  await page.getByRole('heading', { name: '我的情报', exact: true }).waitFor();
  await page.getByRole('button', { name: '重新读取', exact: true }).waitFor({ state: 'visible' });
  if (options.watermark !== false) await page.evaluate(() => {
    const mark = document.createElement('div'); mark.textContent = 'PR5 工程 HTTP mock · 非真实新闻 · 无用户资料';
    mark.style.cssText = 'position:fixed;bottom:0;right:0;background:#fff2cf;color:#553700;padding:5px 12px;z-index:99999;font-size:12px;pointer-events:none'; document.body.appendChild(mark);
  });
  return { page, state, context, close: () => context.close() };
}

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    // Actual server + empty isolated SQLite: no HTTP mocks for intelligence calls.
    {
      const page = await browser.newPage();
      checkAssets(page);
      await page.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin ? route.continue() : route.abort());
      await page.goto(base); await page.getByRole('heading', { name: '暂无真实情报快照' }).waitFor();
      const firstPreference = page.getByRole('button', { name: '保存通用偏好', exact: true });
      if (await firstPreference.count()) await firstPreference.click();
      await page.getByRole('button', { name: '保存预算', exact: true }).waitFor();
      await page.getByRole('button', { name: '生成简报', exact: true }).click();
      await page.getByText(/任务状态：evidence_not_ready/).waitFor();
      assert.equal(await page.locator('.briefing-card').count(), 0);
      checks.push('actual isolated PR4 API: save persona, generate, evidence_not_ready, no fabricated cards'); await page.close();
    }
    {
      const h = await harness(browser, fixtures.real_raw); const { page, state } = h;
      await page.getByText('raw_news_only', { exact: false }).first().waitFor();
      assert.equal(await page.locator('.briefing-card').count(), 0);
      assert.equal(state.requests.length, 0);
      await page.screenshot({ path: path.join(out, 'raw-desktop.png'), fullPage: true });
      await page.getByRole('button', { name: '查看候选证据' }).first().click();
      await page.getByRole('heading', { name: '来源与许可元数据' }).waitFor();
      await page.getByRole('heading', { name: '未验证', exact: true }).waitFor();
      await page.getByRole('button', { name: '关闭详情', exact: true }).click();
      checks.push('actual real-mode raw API fixture: no Focus/Radar, complete archive and historical evidence');
      await page.getByRole('button', { name: '资讯资料库', exact: true }).click();
      await page.getByRole('button', { name: '阅读：' + knownArticle.title, exact: true }).click();
      await page.getByRole('region', { name: '新闻阅读', exact: true }).waitFor();
      await page.getByText('PR5 isolated fetch disabled', { exact: false }).waitFor();
      await page.getByRole('button', { name: '关闭阅读', exact: true }).click();
      for (const name of ['我的关注', '行动日程', '检查记录']) { await page.getByRole('button', { name, exact: true }).click(); await page.getByRole('heading').first().waitFor(); }
      checks.push('legacy NewsLibrary/ArticleReader/GoalWorkspace/calendar/history navigation regression'); await h.close();
    }
    {
      const data = clone(fixtures.real_raw); data.briefing.archive[0].native_tier = 'hold'; data.briefing.archive[0].title = 'UNVERIFIED-HOLD-ASSERTION';
      data.detail.event = clone(data.briefing.archive[0]); data.detail.candidate.rule_item.tier_candidate = 'hold';
      const h = await harness(browser, data); await h.page.getByRole('button', { name: '查看许可元数据' }).click();
      await h.page.getByRole('heading', { name: '来源与许可元数据' }).waitFor();
      assert.equal(await h.page.locator('.briefing-claim,.briefing-citation').count(), 0);
      assert.equal(await h.page.getByText('UNVERIFIED-HOLD-ASSERTION', { exact: true }).count(), 0);
      checks.push('hold-only archive hides assertions/claims/citations and exposes only permitted metadata'); await h.close();
    }
    {
      const h = await harness(browser, fixtures.synthetic);
      await h.page.getByRole('heading', { name: '开发数据已隔离' }).waitFor();
      assert.equal(await h.page.locator('.briefing-card,.briefing-archive article').count(), 0); assert.equal(h.state.requests.length, 0);
      checks.push('synthetic API responses isolated from real home'); await h.close();
    }
    {
      const data = authoredPlan();
      const h = await harness(browser, data, { viewport: { width: 1440, height: 600 } }); const { page, state } = h;
      await page.locator('.briefing-card-title').waitFor();
      assert.equal(await page.locator('.briefing-card-title').evaluate(el => el.getBoundingClientRect().top >= innerHeight), true);
      await pause(800); assert.equal(state.requests.filter(r => r.body.kind === 'rendered').length, 0, 'offscreen DOM mounts must not count');
      await page.locator('.briefing-card-title').scrollIntoViewIfNeeded();
      await page.waitForFunction(() => document.querySelector('.briefing-card-title').getBoundingClientRect().top < innerHeight);
      await pause(950); assert.equal(state.requests.filter(r => r.body.kind === 'rendered').length, 1);
      await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/intelligence/briefings/latest')), page.getByRole('button', { name: '重新读取', exact: true }).click()]);
      await page.waitForFunction(() => [...document.querySelectorAll('button')].find(b => b.textContent === '重新读取')?.disabled === false);
      await page.locator('.briefing-card-title').waitFor(); await page.locator('.briefing-card-title').scrollIntoViewIfNeeded(); await pause(950);
      assert.equal(state.requests.filter(r => r.body.kind === 'rendered').length, 1);
      await page.getByRole('button', { name: '资讯资料库', exact: true }).click();
      await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/intelligence/briefings/latest')), page.getByRole('button', { name: '我的情报', exact: true }).click()]);
      await page.waitForFunction(() => [...document.querySelectorAll('button')].find(b => b.textContent === '重新读取')?.disabled === false);
      await page.locator('.briefing-card-title').waitFor(); await page.locator('.briefing-card-title').scrollIntoViewIfNeeded(); await pause(950);
      assert.equal(state.requests.filter(r => r.body.kind === 'rendered').length, 1);
      assert.equal(state.requests.filter(r => r.body.kind === 'opened').length, 0);
      const open = page.getByRole('button', { name: '核对证据与原文', exact: true });
      await open.click(); await page.getByRole('heading', { name: '快照引用' }).waitFor();
      await pause(100); assert.equal(state.requests.filter(r => r.body.kind === 'opened').length, 1);
      assert.equal(state.requests.filter(r => r.body.kind === 'ack').length, 0);
      await page.getByRole('button', { name: '阅读此历史引用', exact: true }).first().click();
      await page.getByRole('region', { name: '核对本轮证据', exact: true }).waitFor();
      assert.equal(state.readingRequests, 0);
      await page.keyboard.press('Escape'); await page.getByRole('heading', { name: '快照引用' }).waitFor();
      assert.equal(await page.getByRole('button', { name: '阅读此历史引用', exact: true }).first().evaluate(el => document.activeElement === el), true);
      await page.keyboard.press('Escape'); assert.equal(await page.locator('dialog[open]').count(), 0);
      assert.equal(await open.evaluate(el => document.activeElement === el), true);
      state.lostAck = true; state.slowAck = true;
      await page.getByRole('button', { name: '标记已了解', exact: true }).first().click();
      await page.getByText('正在保存反馈…', { exact: true }).waitFor();
      assert.equal(await page.getByRole('button', { name: '标记已了解', exact: true }).first().isDisabled(), true);
      await page.getByRole('button', { name: '重试同一操作', exact: true }).waitFor();
      await page.getByRole('button', { name: '重试同一操作', exact: true }).click();
      await page.getByRole('button', { name: '撤销已了解', exact: true }).waitFor();
      const ackBodies = state.requests.filter(r => r.body.kind === 'ack').map(r => r.body);
      assert.equal(ackBodies.length, 2); assert.deepEqual(ackBodies[0], ackBodies[1]);
      assert.equal(state.data.interactions.filter(r => r.kind === 'ack').length, 1);
      await page.getByRole('button', { name: '撤销已了解', exact: true }).click();
      await page.getByRole('button', { name: '标记已了解', exact: true }).first().waitFor({ state: 'visible' });
      await page.getByRole('button', { name: '暂不感兴趣', exact: true }).first().click();
      await page.getByRole('button', { name: '撤销不感兴趣', exact: true }).waitFor();
      checks.push('real IntersectionObserver: offscreen 0, visible 1, prefetch 0 opened; successful detail opens only');
      checks.push('snapshot reader makes no current reading request; Escape and keyboard focus restore');
      checks.push('lost ack response: exact idempotent retry, one record; explicit dismiss and retract');
      await page.screenshot({ path: path.join(out, 'qualified-http-mock.png'), fullPage: true });
      state.offline = true; await page.getByRole('button', { name: '重新读取', exact: true }).click();
      await page.getByText(/网络连接中断或服务无响应/).first().waitFor();
      assert.equal(await page.locator('.briefing-card').count(), 1);
      state.offline = false; await page.getByRole('button', { name: '重新读取', exact: true }).click();
      await page.getByRole('combobox', { name: '估算阅读预算' }).selectOption('900');
      await page.getByRole('button', { name: '保存预算', exact: true }).click();
      await page.getByText(/偏好已保存/).waitFor();
      await page.waitForFunction(() => document.querySelector('select[aria-label="估算阅读预算"]').value === '900');
      assert.equal(state.data.persona.attention_budget_seconds, 900);
      await page.getByRole('button', { name: '生成简报', exact: true }).waitFor({ state: 'visible' });
      await page.getByRole('combobox', { name: '估算阅读预算' }).selectOption('180');
      await page.getByRole('button', { name: '保存预算', exact: true }).click();
      await page.getByText(/偏好已保存/).waitFor();
      await page.getByRole('button', { name: '生成简报', exact: true }).click();
      await page.getByRole('button', { name: '取消生成', exact: true }).waitFor();
      await page.getByRole('button', { name: '取消生成', exact: true }).click();
      await page.getByText(/取消请求已确认/).waitFor();
      assert.equal(state.data.persona.attention_budget_seconds, 180);
      checks.push('offline retains prior snapshot; budgets 420/900/180; explicit generation and cancel');
      await page.setViewportSize({ width: 390, height: 844 }); await page.evaluate(() => scrollTo(0, 0));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({ path: path.join(out, 'narrow-http-mock.png'), fullPage: true });
      checks.push('390px narrow viewport: no document horizontal overflow'); await h.close();
    }
    {
      const h = await harness(browser, authoredPlan()); const { page, state } = h;
      await page.locator('.briefing-card-title').waitFor(); state.detailFail = true;
      await page.getByRole('button', { name: '核对证据与原文', exact: true }).click();
      await page.getByRole('button', { name: '重读快照', exact: true }).waitFor();
      assert.equal(state.requests.filter(r => r.body.kind === 'opened').length, 0);
      await page.keyboard.press('Escape'); state.detailFail = false; state.conflict = true;
      await page.getByRole('button', { name: '标记已了解', exact: true }).first().click();
      await page.getByText(/G4_SNAPSHOT_VERSION_CONFLICT/).first().waitFor();
      assert.equal(state.requests.filter(r => r.body.kind === 'ack').length, 1);
      assert.equal(state.data.interactions.filter(r => r.kind === 'ack').length, 0);
      checks.push('detail failure never opened; version conflict visible without silent resubmission'); await h.close();
    }
    {
      const data = authoredPlan(); data.briefing.deliveries[0].tier = 'radar'; data.briefing.deliveries[0].status = 'truncated';
      data.briefing.deliveries[0].projection = 'minimum';
      const hiddenRefs = data.briefing.deliveries[0].content_refs.filter(ref => /\/(what_happened|why_it_matters)$/.test(ref));
      data.briefing.deliveries[0].content_refs = data.briefing.deliveries[0].content_refs.filter(ref => !hiddenRefs.includes(ref));
      data.briefing.deliveries[0].omitted_refs = hiddenRefs;
      data.briefing.archive[0].native_tier = 'radar'; data.detail.event = clone(data.briefing.archive[0]); data.detail.candidate.rule_item.tier_candidate = 'radar';
      data.detail.candidate.rule_item.headline.text = '超长标题'.repeat(1000); data.detail.candidate.rule_item.what_happened.text = '长内容状态仍可阅读。'.repeat(500);
      const excluded = { ...data.briefing.archive[0], id: 'excluded-id', event_key: 'excluded-event', event_snapshot_id: 'excluded-snapshot', reason_codes: ['not_budget_eligible'] };
      data.briefing.archive.push(excluded); data.briefing.budget_diagnostics.excluded_event_keys = [excluded.event_key];
      const h = await harness(browser, data); await h.page.locator('.tier-radar .briefing-card-title').waitFor();
      await h.page.getByText('truncated · 预算内精简展示，完整材料可在证据详情查看。', { exact: true }).waitFor();
      assert.equal(await h.page.locator('.briefing-archive .badge').filter({ hasText: /^excluded$/ }).count(), 1);
      await h.page.setViewportSize({ width: 390, height: 844 });
      assert.equal(await h.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      checks.push('Radar/truncated/excluded and long title/body remain readable at 390px'); await h.close();
    }
    {
      const data = authoredPlan(); data.previous = clone(data.briefing); data.previous.id = 'old-mock';
      data.previous.archive[0].event_revision = 'f'.repeat(64); data.previous.archive[0].title = 'Historical fixture title';
      data.previousDetail = clone(data.detail); data.previousDetail.briefing_id = 'old-mock';
      data.previousDetail.event = clone(data.previous.archive[0]); data.previousDetail.candidate.event.event_revision = 'f'.repeat(64);
      data.previousDetail.candidate.rule_item.event_revision = 'f'.repeat(64);
      data.previousDetail.documents[0].content.paragraphs[0] = 'Historical quote 😊 version-one';
      data.previousDetail.citations[0].quote = 'Historical quote 😊 version-one'; data.previousDetail.citations[0].start = 0;
      data.previousDetail.citations[0].end = Array.from(data.previousDetail.citations[0].quote).length;
      data.previousDetail.claims[0].marker = 'withdrawal'; data.detail.claims[0].marker = 'correction';
      data.interactions = [{ id: 'prior-render', kind: 'rendered', briefing_id: 'old-mock', sequence: 5, available_at: data.briefing.generated_at },
        { id: 'later-include', kind: 'included', briefing_id: data.briefing.id, sequence: 9, available_at: data.briefing.generated_at }];
      const h = await harness(browser, data); const { page, state } = h;
      await page.getByText(/修订变化 1/).waitFor();
      await page.getByRole('button', { name: '核对证据与原文', exact: true }).click();
      await page.getByText(/更正记录/).waitFor(); await page.keyboard.press('Escape');
      await page.getByRole('textbox', { name: '历史快照 ID' }).fill('old-mock');
      await page.getByRole('button', { name: '打开历史快照', exact: true }).click();
      await page.getByText(/正在查看历史快照 old-mock/).waitFor();
      await page.getByRole('button', { name: '查看候选证据', exact: true }).first().click();
      await page.getByText('Historical quote 😊 version-one', { exact: true }).waitFor();
      await page.getByText(/撤回记录/).waitFor();
      await page.getByRole('button', { name: '阅读此历史引用', exact: true }).first().click();
      await page.getByRole('region', { name: '核对本轮证据', exact: true }).getByText('Historical quote 😊 version-one', { exact: true }).waitFor();
      assert.equal(state.readingRequests, 0);
      await page.screenshot({ path: path.join(out, 'historical-evidence-http-mock.png') });
      checks.push('last observed snapshot vs included; revision delta; correction/withdrawal; Unicode historical citation and immutable reader'); await h.close();
    }
    {
      const data = clone(fixtures.real_raw); const seed = data.briefing.archive[0];
      data.briefing.archive = Array.from({ length: 100 }, (_, i) => ({ ...seed, id: 'archive-' + i, event_key: 'event-' + i, event_snapshot_id: 'snapshot-' + i }));
      const h = await harness(browser, data); await h.page.locator('.briefing-archive article').last().waitFor();
      assert.equal(await h.page.locator('.briefing-archive article').count(), 100);
      h.state.permissionDenied = true; await h.page.getByRole('button', { name: '重新读取', exact: true }).click();
      await h.page.getByText(/权限不足/).first().waitFor();
      assert.equal(await h.page.getByRole('button', { name: '生成简报', exact: true }).isDisabled(), true);
      assert.equal(await h.page.getByRole('button', { name: '保存预算', exact: true }).isDisabled(), true);
      assert.equal(h.state.requests.length, 0);
      checks.push('100 archive candidates preserved; permission denial visible without mutation'); await h.close();
    }
    for (const status of [{ enabled: false, state: 'disabled' }, { ...authoredPlan().status, state: 'migration_required', code: 'G4_PERSISTENCE_MIGRATION_REQUIRED' }]) {
      const d = authoredPlan(); d.status = status;
      const h = await harness(browser, d); await h.page.getByText(/情报服务尚未/).first().waitFor();
      assert.equal(await h.page.locator('.briefing-card').count(), 0); assert.equal(h.state.requests.length, 0); await h.close();
    }
    checks.push('disabled and migration-required states remain read-only with raw-library access');
    // Review regressions: native history comes from isolated real API runs; the
    // real-shaped route is a UI mock, not evidence of qualified production news.
    for (const lifecycle of ['superseded', 'retracted']) {
      const native = fixtures.native_history[lifecycle];
      const data = realFixture(native.changed);
      data.previous = realFixture(native.old.briefing); data.previous.id = 'old-mock';
      data.previousDetail = realFixture(native.old.detail); data.previousDetail.briefing_id = 'old-mock';
      const oldClaim = native.old.detail.claims[0];
      // Also defend against an old server returning the full appended history.
      data.detail.assessments = [...realFixture(native.old.detail.assessments), ...data.detail.assessments];
      const h = await harness(browser, data); const { page } = h;
      await page.getByRole('button', { name: '查看候选证据', exact: true }).first().click();
      const claim = page.locator('.briefing-claim').filter({ has: page.getByText(oldClaim.statement, { exact: true }) });
      await claim.getByText(lifecycle === 'superseded' ? '已被更正取代（superseded）' : '已撤回（retracted）', { exact: true }).waitFor();
      await page.keyboard.press('Escape');
      await page.getByRole('textbox', { name: '历史快照 ID' }).fill('old-mock');
      await page.getByRole('button', { name: '打开历史快照', exact: true }).click();
      await page.getByText(/正在查看历史快照 old-mock/).waitFor();
      await page.getByRole('button', { name: '查看候选证据', exact: true }).first().click();
      await page.locator('.briefing-claim').filter({ has: page.getByText(oldClaim.statement, { exact: true }) }).getByText('当前主张', { exact: true }).waitFor();
      checks.push('native old/current snapshot vs ' + lifecycle + ' snapshot assessment'); await h.close();
    }
    for (const origin of ['item', 'claim', 'citation', 'presentation']) {
      const data = authoredPlan();
      if (origin === 'item') data.detail.candidate.rule_item.record_origin = 'synthetic';
      if (origin === 'claim') data.detail.claims[0].record_origin = 'synthetic';
      if (origin === 'citation') data.detail.citations[0].record_origin = 'synthetic';
      if (origin === 'presentation') data.detail.candidate.presentation.base_item.record_origin = 'synthetic';
      const h = await harness(browser, data); const { page, state } = h;
      await page.getByRole('button', { name: '查看候选证据', exact: true }).first().click();
      await page.getByText(/派生证据来源不一致/).waitFor();
      assert.equal(await page.locator('dialog .briefing-claim,dialog .briefing-citation,dialog .briefing-feedback').count(), 0);
      await page.getByRole('heading', { name: '来源与许可元数据', exact: true }).waitFor();
      assert.equal(state.requests.filter(r => ['ack', 'opened', 'rendered'].includes(r.body.kind)).length, 0);
      checks.push('mixed ' + origin + ' origin isolated to safe metadata without feedback'); await h.close();
    }
    for (const projection of ['focus', 'radar', 'minimum']) {
      const data = authoredPlan(); const delivery = data.briefing.deliveries[0];
      delivery.projection = projection; delivery.tier = projection === 'radar' ? 'radar' : 'focus';
      delivery.status = projection === 'minimum' ? 'truncated' : delivery.tier;
      const omitted = delivery.content_refs.filter(ref => projection !== 'focus' && ref.endsWith('/why_it_matters') || projection === 'minimum' && ref.endsWith('/what_happened'));
      delivery.content_refs = delivery.content_refs.filter(ref => !omitted.includes(ref)); delivery.omitted_refs = omitted;
      const h = await harness(browser, data); const { page } = h;
      await page.locator('.briefing-card-title').waitFor(); const card = page.locator('.briefing-card');
      assert.equal(await card.getByText('发生了什么', { exact: true }).count(), projection === 'minimum' ? 0 : 1);
      assert.equal(await card.getByText('为什么重要', { exact: false }).count(), projection === 'focus' ? 1 : 0);
      await page.getByText(new RegExp('估算已用 ' + data.briefing.budget_diagnostics.used_seconds + ' 秒 / 剩余 ' + data.briefing.budget_diagnostics.unused_seconds + ' 秒')).waitFor();
      await page.getByRole('button', { name: '核对证据与原文', exact: true }).click();
      await page.getByRole('heading', { name: '为什么重要（推断）', exact: true }).waitFor();
      checks.push(projection + ' projection matches refs; complete content available only in detail; budget used/unused visible'); await h.close();
    }
    {
      const h = await harness(browser, fixtures.real_raw); const { page, state } = h;
      await page.getByText('估算已用 / 剩余：未计算', { exact: true }).waitFor();
      state.malformed = true; await page.getByRole('button', { name: '重新读取', exact: true }).click();
      await page.getByText(/返回数据结构异常/).waitFor();
      await page.getByRole('button', { name: '资讯资料库', exact: true }).click();
      await page.getByRole('button', { name: '阅读：' + knownArticle.title, exact: true }).waitFor();
      state.malformed = false; await page.getByRole('button', { name: '我的情报', exact: true }).click();
      await page.getByText('估算已用 / 剩余：未计算', { exact: true }).waitFor();
      checks.push('malformed coverage rejected before rendering; old navigation and library retained; reread recovers'); await h.close();
    }
    {
      const page = await browser.newPage(); await page.goto(process.env.CFAW_QA_BOUNDARY_URL);
      await page.getByRole('heading', { name: '情报页面暂时无法显示', exact: true }).waitFor();
      await page.getByRole('navigation', { name: '旧导航' }).waitFor();
      await page.getByRole('button', { name: '打开原始资讯库', exact: true }).click(); await page.getByText('资料库可用', { exact: true }).waitFor();
      await page.getByRole('button', { name: '修复测试输入', exact: true }).click();
      await page.getByRole('button', { name: '重试情报页面', exact: true }).click(); await page.getByText('情报重试成功', { exact: true }).waitFor();
      checks.push('actual local ErrorBoundary catches render failure, retains navigation/library and remounts on retry'); await page.close();
    }
    {
      const h = await harness(browser, fixtures.real_raw); const {page,state}=h;
      const summaries=Array.from({length:21},(_,i)=>({id:'directory-fixture-'+(21-i),version:21-i,as_of:fixtures.real_raw.briefing.as_of,generated_at:fixtures.real_raw.briefing.generated_at,evidence_status:'raw_news_only'}));
      await page.route('**/api/intelligence/briefings?*', route=> {
        const q=new URL(route.request().url()).searchParams;
        if(q.has('before_version')) {assert.equal(q.get('before_version'),'2');assert.equal(q.get('through_version'),'21');}
        return route.fulfill({contentType:'application/json',body:JSON.stringify({stream_id:state.data.status.head.stream_id,through_version:21,items:q.has('before_version')?summaries.slice(20):summaries.slice(0,20),next_before_version:q.has('before_version')?null:2})});
      });
      await page.getByRole('button',{name:'重新读取',exact:true}).click();
      await page.getByRole('button',{name:'打开历史简报 V21',exact:true}).waitFor();
      assert.equal(await page.getByRole('button',{name:'打开历史简报 V1',exact:true}).count(),0);
      await page.getByRole('button',{name:'加载更早快照',exact:true}).click();
      await page.getByRole('button',{name:'打开历史简报 V1',exact:true}).waitFor();
      assert.equal(await page.getByRole('button',{name:'加载更早快照',exact:true}).count(),0);
      assert.equal(state.requests.filter(r=>r.body.kind==='opened'||r.body.kind==='ack'||r.body.kind==='rendered').length,0);
      checks.push('authored directory UI pagination preserves upper-version cursor and does not infer card exposure/knowledge'); await h.close();
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(assetErrors, []);
    const result = { status: 'PASS', browser: 'Microsoft Edge headless / Playwright', checks, console_page_errors: errors, static_resource_errors: assetErrors,
      record_origin: 'authored_engineering_mock', live_news: false, live_model: false, production_database_used: false,
      qualified_real_pipeline_tested: false, screenshots: ['raw-desktop.png', 'qualified-http-mock.png', 'narrow-http-mock.png', 'historical-evidence-http-mock.png'] };
    fs.writeFileSync(path.join(out, 'browser-results.json'), JSON.stringify(result, null, 2));
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  } finally { await browser.close(); }
})().catch(error => { fs.writeFileSync(path.join(out, 'browser-failure.txt'), String(error.stack)); process.stderr.write(String(error.stack) + '\n'); process.exitCode = 1; });
