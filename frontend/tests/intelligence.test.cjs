// UI policy/API tests. Node 24's built-in TS transform; no added dependencies.
const { test } = require('node:test');
const assert = require('node:assert/strict');
require('node:module').registerHooks({ resolve(specifier, context, next) {
  try { return next(specifier, context); } catch (error) {
    if (specifier.startsWith('.') && !/\.(ts|js|json)$/.test(specifier)) return next(specifier + '.ts', context);
    throw error;
  }
} });
const policy = require('../src/intelligence.ts');
const { ApiError } = require('../src/api.ts');
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const originalFetch = global.fetch;
const state = (seq = 1, epoch = 'e1') => ({ state: 'ready', mode: 'real', head: { sequence: seq, sha256: 'head' + seq, epoch } });
test.afterEach(() => { global.fetch = originalFetch; });

test('delivery requires a real plan, matching immutable identity, rights and native eligibility', () => {
  const event = { event_snapshot_id: 's1', event_key: 'e1', event_revision: 'v1', native_tier: 'focus', evidence_status: 'attributed', rights: ['permitted'], content_kinds: ['publisher_text'] };
  const delivery = { ...event, id: 'd1' };
  const briefing = { mode: 'real', evidence_status: 'plan_ready', display_order: ['e1'] };
  assert.equal(policy.eligibleDelivery(briefing, delivery, event), true);
  for (const patch of [{ mode: 'synthetic_development' }, { evidence_status: 'raw_news_only' }, { display_order: [] }])
    assert.equal(policy.eligibleDelivery({ ...briefing, ...patch }, delivery, event), false);
  for (const patch of [{ native_tier: 'hold' }, { event_revision: 'later' }, { rights: [] }, { rights: ['unknown'] }, { content_kinds: ['synthetic_text'] }, { evidence_status: 'unverified' }])
    assert.equal(policy.eligibleDelivery(briefing, delivery, { ...event, ...patch }), false);
  assert.equal(policy.eligibleDelivery(briefing, delivery), false);
});
test('included is never the visit baseline; snapshot revisions are compared without knowledge claims', () => {
  const rows = [{ kind: 'included', id: 1 }, { kind: 'opened', id: 2 }, { kind: 'included', id: 3 }];
  assert.equal(policy.visitBaseline(rows).id, 2);
  assert.equal(policy.visitBaseline([{ kind: 'included' }]), undefined);
  const row = (key, rev) => ({ event_key: key, event_revision: rev });
  assert.deepEqual(policy.changesSince({ archive: [row('a', '2'), row('b', '1'), row('c', '1')] },
    { archive: [row('a', '1'), row('b', '1'), row('d', '1')] }), { added: 1, changed: 1, same: 1, absent: 1 });
});
test('retraction only negates explicitly selected feedback, never turns opened into ack', () => {
  const row = (id, kind, retracts_id) => ({ id, kind, retracts_id, briefing_id: 'b', target_id: 't' });
  const rows = [row('open', 'opened'), row('a', 'ack'), row('d', 'dismiss'), row('r', 'retract', 'a')];
  assert.deepEqual(policy.activeFeedback(rows, 'b', 't').map(r => r.id), ['d']);
});
test('unsafe URLs and evidence certainty stay explicit', () => {
  for (const link of ['javascript:alert(1)', 'data:text/html,x', 'https://user:pass@example.com', 'synthetic://foo']) assert.equal(policy.safeUrl(link), undefined);
  assert.equal(policy.safeUrl('https://example.com/a'), 'https://example.com/a');
  assert.match(policy.evidenceLabel('source_attributed'), /尚未独立验证/);
  assert.match(policy.evidenceLabel('attributed'), /主张验证状态见详情/);
  assert.match(policy.evidenceLabel('independently_supported'), /不等于事实真值/);
});
test('detail binding rejects different snapshots, revisions, future documents and synthetic origins', () => {
  const event = { event_snapshot_id: 's1', event_key: 'e1', event_revision: 'v1', native_tier: 'focus', rights: ['permitted'], evidence_status: 'attributed' };
  const briefing = { id: 'b1', version: 1, as_of: '2026-01-02T00:00:00Z' };
  const detail = { briefing_id: 'b1', snapshot_version: 1, as_of: briefing.as_of, event,
    candidate: { snapshot: { snapshot_id: 's1' }, event: { event_key: 'e1', event_revision: 'v1' }, rule_item: { record_origin: 'real', event_key: 'e1', event_revision: 'v1' } }, claims: [], citations: [],
    documents: [{ record_origin: 'real', rights: 'permitted', available_at: '2026-01-01T00:00:00Z' }] };
  assert.equal(policy.safeDetail(detail, briefing, event), true);
  for (const patch of [{ snapshot_version: 2 }, { briefing_id: 'b2' }, { event: { ...event, event_revision: 'v2' } },
    { candidate: { ...detail.candidate, rule_item: { ...detail.candidate.rule_item, record_origin: 'synthetic' } } },
    { claims: [{ record_origin: 'synthetic' }] }, { citations: [{ record_origin: 'synthetic' }] },
    { documents: [{ ...detail.documents[0], record_origin: 'synthetic' }] }, { documents: [{ ...detail.documents[0], available_at: '2026-01-03T00:00:00Z' }] }])
    assert.equal(policy.safeDetail({ ...detail, ...patch }, briefing, event), false);
});

test('wire validation rejects malformed nested snapshots before a successful fetch can reach React', async () => {
  const { validWire } = require('../src/intelligenceValidation.ts');
  const now = '2026-01-01T00:00:00Z';
  const value = { schema_revision: 'g4-pr4-briefing-v1', id: 'b', run_id: 'r', version: 1, etag: 'etag', as_of: now, generated_at: now,
    mode: 'real', evidence_status: 'raw_news_only', persona_version_id: 'p', runtime_sha256: 'a'.repeat(64), runtime_policy_sha256: 'a'.repeat(64),
    reason_codes: [], archive_snapshot_ids: [], unmet_protected_event_keys: [], display_order: [], deliveries: [], archive: [], budget_diagnostics: null,
    coverage: { requested_start_at: now, requested_end_at: now, windows: [], status_counts: {}, source_count: 0, window_count: 0,
      missing_source_ids: [], unobserved_source_ids: [], sources: [], effective_statuses: [], has_gap: true } };
  assert.equal(validWire('BriefingView', value), true);
  for (const patch of [{ coverage: undefined }, { coverage: { ...value.coverage, sources: 'invalid' } }, { archive: [{}] }, { version: 0 }])
    assert.equal(validWire('BriefingView', { ...value, ...patch }), false);
  global.fetch = async () => json({ ...value, coverage: undefined });
  await assert.rejects(policy.getIntelligence('/briefings/latest'), e => e instanceof ApiError && e.code === 'G4_RESPONSE_SCHEMA_INVALID');
  global.fetch = async () => json(value);
  assert.deepEqual(await policy.getIntelligence('/briefings/latest'), value);
});
test('lost response retries preserve the same key and complete body', async () => {
  const bodies = []; let posts = 0;
  global.fetch = async (url, options) => {
    if (url.endsWith('/status')) return json(state());
    bodies.push(options.body);
    if (++posts === 1) throw new TypeError('lost response after commit');
    return json({ resource_id: 'ack1', deduplicated: true, head: {} });
  };
  const job = policy.intent('/interactions', { kind: 'ack', target_id: 't' });
  await assert.rejects(policy.writeIntent(job));
  const receipt = await policy.writeIntent(job);
  assert.equal(receipt.deduplicated, true);
  assert.equal(bodies[0], bodies[1]);
});
test('concurrent intents serialize and acquire the next head only after prior completion', async () => {
  const events = []; let seq = 1;
  global.fetch = async (url, options) => {
    if (url.endsWith('/status')) { events.push('get' + seq); return json(state(seq)); }
    const body = JSON.parse(options.body); events.push(body.kind + ':' + body.expected_head); seq++;
    return json({ resource_id: String(seq), head: {}, deduplicated: false });
  };
  await Promise.all([policy.writeIntent(policy.intent('/interactions', { kind: 'ack' })), policy.writeIntent(policy.intent('/interactions', { kind: 'dismiss' }))]);
  assert.deepEqual(events, ['get1', 'ack:head1', 'get2', 'dismiss:head2']);
});
test('only an unchanged expected-head conflict may rebase in the same epoch', async () => {
  let gets = 0; const bodies = [];
  global.fetch = async (url, options) => {
    if (url.endsWith('/status')) return json(state(++gets));
    bodies.push(JSON.parse(options.body));
    return bodies.length === 1 ? json({ code: 'G4_EXPECTED_HEAD_CONFLICT', database_state: 'unchanged' }, 409) : json({ resource_id: 'a', head: {}, deduplicated: false });
  };
  await policy.writeIntent(policy.intent('/interactions', { kind: 'ack' }));
  assert.equal(bodies[0].idempotency_key, bodies[1].idempotency_key);
  assert.equal(bodies[1].expected_head, 'head2');
});
test('epoch change and semantic version conflicts are never silently adopted', async () => {
  let gets = 0; let posts = 0;
  global.fetch = async url => url.endsWith('/status') ? json(state(1, ++gets === 1 ? 'old' : 'new'))
    : (++posts, json({ code: 'G4_EXPECTED_HEAD_CONFLICT', database_state: 'unchanged' }, 409));
  await assert.rejects(policy.writeIntent(policy.intent('/interactions', { kind: 'ack' })), e => e instanceof ApiError && e.code === 'G4_EPOCH_CHANGED');
  assert.equal(posts, 1);
  posts = 0;
  global.fetch = async url => url.endsWith('/status') ? json(state())
    : (++posts, json({ code: 'G4_SNAPSHOT_VERSION_CONFLICT', database_state: 'unchanged' }, 409));
  await assert.rejects(policy.writeIntent(policy.intent('/interactions', { kind: 'ack' })), e => e.code === 'G4_SNAPSHOT_VERSION_CONFLICT');
  assert.equal(posts, 1);
});
test('card detail prefetch bounds concurrency and never starts an aborted queued request', async () => {
  let active = 0; let peak = 0; let calls = 0; const releases = [];
  global.fetch = async () => {
    calls++; active++; peak = Math.max(peak, active);
    await new Promise(resolve => releases.push(resolve)); active--;
    return json({});
  };
  const controllers = Array.from({ length: 6 }, () => new AbortController());
  const complete = Promise.allSettled(controllers.map((c, i) => policy.getCardDetail('/events/detail?test=' + i, c.signal)));
  controllers[2].abort();
  assert.equal(calls, 2);
  for (let i = 0; i < 6; i++) { releases.splice(0).forEach(r => r()); await new Promise(resolve => setImmediate(resolve)); }
  const results = await complete;
  assert.equal(peak, 2); assert.equal(calls, 5);
  assert.equal(results.filter(r => r.status === 'rejected' && r.reason.name === 'AbortError').length, 1);
});

test('latest assessment respects as_of, append ties, unsorted inputs and all retired lifecycle labels', () => {
  const old = { claim_key: 'c', as_of: '2026-01-01T00:00:00Z', lifecycle: 'current' };
  const changed = { ...old, as_of: '2026-01-02T00:00:00Z', lifecycle: 'superseded' };
  const retracted = { ...changed, lifecycle: 'retracted' };
  assert.equal(policy.latestAssessment([old, changed], 'c', old.as_of), old);
  assert.equal(policy.latestAssessment([changed, old], 'c', changed.as_of), changed);
  assert.equal(policy.latestAssessment([old, changed, retracted], 'c', changed.as_of), retracted);
  const micros = { ...old, as_of: '2026-01-01T00:00:00.000001Z' };
  assert.equal(policy.latestAssessment([old, micros], 'c', '2026-01-01T00:00:00.000000Z'), old);
  for (const label of ['historical', 'superseded', 'retracted']) assert.match(policy.lifecycleLabel(label), new RegExp(label));
});

test('observation intent survives remounts, coalesces concurrent requests and retries a lost response with the same key', async () => {
  const briefing = { id: 'observation-test', version: 1 }; const bodies = []; let lost = true;
  global.fetch = async (url, options) => {
    if (url.endsWith('/status')) return json(state());
    bodies.push(options.body);
    if (lost) { lost = false; throw new TypeError('response lost'); }
    return json({ resource_id: 'observed', deduplicated: true, head: {} });
  };
  const job = policy.observationIntent(briefing, 'd1', 'rendered');
  await assert.rejects(policy.writeIntent(job));
  assert.equal(policy.observationIntent(briefing, 'd1', 'rendered'), job);
  await Promise.all([policy.writeIntent(job), policy.writeIntent(policy.observationIntent(briefing, 'd1', 'rendered'))]);
  await policy.writeIntent(policy.observationIntent(briefing, 'd1', 'rendered'));
  assert.equal(bodies.length, 2); assert.equal(bodies[0], bodies[1]);
});

test('native projection refs determine the blocks and reject missing or contradictory projection', () => {
  const base = '/history_input/replay/candidates/0/rule_item/';
  const item = { headline: { text: 'title' }, what_happened: { text: 'what' }, why_it_matters: { text: 'why' },
    claim_summaries: [], risks: [], uncertainties: [] };
  const detail = { candidate: { rule_item: item } };
  for (const [projection, refs, what, why] of [['focus', ['headline', 'what_happened', 'why_it_matters'], true, true],
    ['radar', ['headline', 'what_happened'], true, false], ['minimum', ['headline'], false, false]]) {
    const result = policy.projectedItem(detail, { projection, content_refs: refs.map(r => base + r), omitted_refs: [] });
    assert.equal(!!result.what, what); assert.equal(!!result.why, why);
  }
  assert.equal(policy.projectedItem(detail, { projection: null, content_refs: [] }), null);
  assert.equal(policy.projectedItem(detail, { projection: 'minimum', content_refs: [base + 'why_it_matters'] }), null);
});
