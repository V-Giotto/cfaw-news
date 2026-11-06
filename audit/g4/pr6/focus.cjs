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
    const h = await harness(browser, authoredPlan()); const { page } = h;
    assert(await page.locator('script[src="/@vite/client"]').count(), 'actual development server required');
    const open = page.getByRole('button', { name: '核对证据与原文', exact: true });
    for (let i = 0; i < 3; i++) {
      await open.click(); await page.getByRole('heading', { name: '快照引用', exact: true }).waitFor();
      const read = page.getByRole('button', { name: '阅读此历史引用', exact: true }).first();
      await read.click(); await page.getByRole('region', { name: '核对本轮证据', exact: true }).waitFor();
      await page.keyboard.press('Escape'); await page.getByRole('heading', { name: '快照引用', exact: true }).waitFor();
      assert(await read.evaluate(el => el === document.activeElement), 'reader Escape must restore citation trigger');
      await page.keyboard.press('Escape'); await page.waitForTimeout(100);
      const focus = await open.evaluate(el => ({ restored: el === document.activeElement, actual: document.activeElement?.tagName }));
      assert(focus.restored, 'development StrictMode focus lost to ' + focus.actual);
      await open.click(); await page.getByRole('heading', { name: '快照引用', exact: true }).waitFor();
      await page.getByRole('button', { name: '关闭详情', exact: true }).click(); await page.waitForTimeout(100);
      assert(await open.evaluate(el => el === document.activeElement), 'close button must restore first trigger');
    }
    assert.equal(h.state.readingRequests, 0); assert.deepEqual(errors, []); assert.deepEqual(assetErrors, []);
    const result = { status: 'PASS', browser_version: browser.version(), development: true, strict_mode: true,
      cycles: 3, checks: ['reader Escape restores citation trigger', 'second Escape restores original list trigger',
      'explicit Close restores original list trigger', 'repeated mount/unmount preserves focus', 'no current body request'],
      fixtures_sha256: require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(out, 'fixtures.json'))).digest('hex') };
    await page.screenshot({ path: path.join(out, 'strict-focus.png'), fullPage: true });
    fs.writeFileSync(path.join(out, 'focus-result.json'), JSON.stringify(result, null, 2));
    process.stdout.write(JSON.stringify(result)); await h.close();
  } finally { await browser.close(); }
})().catch(e => { fs.writeFileSync(path.join(out, 'focus-failure.txt'), String(e.stack)); process.stderr.write(String(e.stack)); process.exitCode = 1; });
