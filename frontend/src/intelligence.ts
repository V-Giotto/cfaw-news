import { api, ApiError } from './api'
import type { ArchiveView, BriefingView, DeliveryView, DisabledStatus, EventDetailView, InteractionView,
  MutationView, PersonaView, StatusView, ClaimAssessment } from './intelligence.generated'
import { validWire } from './intelligenceValidation'

export type Status = StatusView | DisabledStatus
export async function getIntelligence<T>(path: string, signal?: AbortSignal): Promise<T> {
  const value = await api<T>('/intelligence' + path, {
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
  })
  const schema = path === '/briefings' || path.startsWith('/briefings?') ? 'SnapshotPage'
    : path.startsWith('/visits/latest') && value !== null ? 'VisitView'
    : path.startsWith('/briefings/') ? 'BriefingView' : path.startsWith('/events/detail?') ? 'EventDetailView' : null
  if (schema && !validWire(schema, value)) throw new ApiError(422, 'G4_RESPONSE_SCHEMA_INVALID', 'unchanged')
  return value
}
const postIntelligence = (job: WriteIntent) => api<MutationView>('/intelligence' + job.path, {
  method: 'POST', body: JSON.stringify(job.body), signal: AbortSignal.timeout(20000),
})
// Keep card prefetches below the PR4 boundary's four concurrent requests.
// Queued reads are cancelled before network access when their page is hidden.
let detailReads = 0
const detailQueue: Array<() => void> = []
export function getCardDetail(path: string, signal: AbortSignal): Promise<EventDetailView> {
  return new Promise((resolve, reject) => {
    const start = () => {
      if (signal.aborted) { reject(new DOMException('Aborted', 'AbortError')); drain(); return }
      detailReads++
      void getIntelligence<EventDetailView>(path, signal).then(resolve, reject).finally(() => { detailReads--; drain() })
    }
    const drain = () => { while (detailReads < 2 && detailQueue.length) detailQueue.shift()!() }
    detailQueue.push(start); drain()
  })
}
export const readyReal = (s: Status | null): s is StatusView => !!s && s.state === 'ready' && 'mode' in s && s.mode === 'real' && !!s.head
export const safeUrl = (value: string | null | undefined): string | undefined => {
  try { const u = new URL(value || ''); return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password ? u.href : undefined } catch { return undefined }
}
export function errorText(error: unknown): string {
  if (!(error instanceof ApiError)) return '网络连接中断或服务无响应。已保留当前快照，请检查连接后重试。'
  if (error.code === 'G4_RESPONSE_SCHEMA_INVALID') return '返回数据结构异常，已停止显示新快照。请重新读取或进入原始资讯库。'
  const prefix = error.status === 403 ? '权限不足：本地访问边界拒绝请求。'
    : error.status === 409 ? '版本冲突：请重新读取状态；旧快照仍保留。'
    : error.status === 429 ? '服务容量已满，请稍后重试。'
    : error.status === 503 ? '情报服务暂不可用，需要检查本地服务状态。'
    : '操作未完成。'
  return prefix + '（' + error.code + '）'
}
export function notFound(error: unknown, code: string) { return error instanceof ApiError && error.status === 404 && error.code === code }

// Each intent retains its key and exact semantic payload after a lost response.
// Writes serialize across cards and dialogs. Only an unchanged-head conflict may rebase,
// within the same epoch; snapshot/persona/run conflicts always reach the user.
export interface WriteIntent { path: string; payload: Record<string, unknown>; body?: Record<string, unknown> }
export const intent = (path: string, payload: Record<string, unknown>): WriteIntent => ({ path,
  payload: { schema_revision: 'g4-pr4-write-v1', idempotency_key: crypto.randomUUID(), ...payload } })
let tail: Promise<unknown> = Promise.resolve()
const observations = new Map<string, WriteIntent>()
const observationResults = new WeakMap<WriteIntent, Promise<MutationView>>()
export function observationIntent(briefing: BriefingView, targetId: string, kind: 'rendered' | 'opened'): WriteIntent {
  const key = JSON.stringify([briefing.id, targetId, kind])
  let job = observations.get(key)
  if (!job) {
    job = intent('/interactions', { briefing_id: briefing.id, expected_snapshot_version: briefing.version,
      target_id: targetId, kind, confirmation: kind === 'rendered' ? 'viewport_visible' : 'detail_opened' })
    observations.set(key, job)
  }
  return job
}
export function writeIntent(job: WriteIntent): Promise<MutationView> {
  const observation = job.payload.kind === 'rendered' || job.payload.kind === 'opened'
  if (observation && observationResults.has(job)) return observationResults.get(job)!
  const operation = async () => {
    if (!job.body) {
      const state = await getIntelligence<Status>('/status')
      if (!readyReal(state)) throw new ApiError(503, 'G4_REAL_SERVICE_NOT_READY')
      job.body = { ...job.payload, expected_head: state.head!.sha256, expected_epoch: state.head!.epoch }
    }
    try { return await postIntelligence(job) }
    catch (error) {
      if (!(error instanceof ApiError) || error.code !== 'G4_EXPECTED_HEAD_CONFLICT' || error.databaseState !== 'unchanged') throw error
      const state = await getIntelligence<Status>('/status')
      if (!readyReal(state) || state.head!.epoch !== job.body.expected_epoch) throw new ApiError(409, 'G4_EPOCH_CHANGED')
      job.body = { ...job.body, expected_head: state.head!.sha256 }
      return postIntelligence(job)
    }
  }
  const result = tail.then(operation, operation)
  tail = result.catch(() => undefined)
  if (observation) {
    observationResults.set(job, result)
    void result.catch(() => { observationResults.delete(job) })
  }
  return result
}

export async function readInteractions(signal?: AbortSignal): Promise<{ rows: InteractionView[]; complete: boolean }> {
  const rows: InteractionView[] = []
  // Explicit API pagination bound; never silently interpret a partial history as no visits.
  for (let offset = 0; offset <= 20000; offset += 500) {
    const page = await getIntelligence<InteractionView[]>('/interactions?limit=500&offset=' + offset, signal)
    rows.push(...page)
    if (page.length < 500) return { rows, complete: true }
  }
  return { rows, complete: false }
}

export const observed = (row: InteractionView) => ['rendered', 'opened', 'ack', 'dismiss'].includes(row.kind)
export function visitBaseline(rows: InteractionView[]): InteractionView | undefined { return rows.filter(observed).at(-1) }
export function changesSince(current: BriefingView, previous: BriefingView) {
  const prior = new Map(previous.archive.map(a => [a.event_key, a.event_revision]))
  return {
    added: current.archive.filter(a => !prior.has(a.event_key)).length,
    changed: current.archive.filter(a => prior.has(a.event_key) && prior.get(a.event_key) !== a.event_revision).length,
    same: current.archive.filter(a => prior.get(a.event_key) === a.event_revision).length,
    absent: previous.archive.filter(a => !current.archive.some(b => b.event_key === a.event_key)).length,
  }
}
export function eligibleDelivery(briefing: BriefingView, delivery: DeliveryView, archive?: ArchiveView): boolean {
  return briefing.mode === 'real' && briefing.evidence_status === 'plan_ready' && !!archive
    && briefing.display_order.includes(delivery.event_key)
    && archive.event_snapshot_id === delivery.event_snapshot_id && archive.event_key === delivery.event_key
    && archive.event_revision === delivery.event_revision && archive.native_tier !== 'hold'
    && ['attributed', 'source_attributed', 'independently_supported'].includes(archive.evidence_status)
    && archive.rights.length > 0 && archive.rights.every(r => ['permitted', 'excerpt_only'].includes(r))
    && archive.content_kinds?.length > 0 && archive.content_kinds.every(k => ['feed_summary', 'publisher_text'].includes(k))
}
export function boundDetail(detail: EventDetailView, briefing: BriefingView, event: ArchiveView): boolean {
  return detail.briefing_id === briefing.id && detail.snapshot_version === briefing.version
    && detail.as_of === briefing.as_of && detail.event.event_snapshot_id === event.event_snapshot_id
    && detail.event.event_revision === event.event_revision && detail.event.event_key === event.event_key
    && detail.event.native_tier === event.native_tier && JSON.stringify(detail.event.rights) === JSON.stringify(event.rights)
    && detail.event.evidence_status === event.evidence_status
    && detail.candidate.snapshot.snapshot_id === event.event_snapshot_id
    && detail.candidate.event.event_key === event.event_key && detail.candidate.event.event_revision === event.event_revision
    && detail.candidate.rule_item.event_key === event.event_key && detail.candidate.rule_item.event_revision === event.event_revision
    && detail.documents.length > 0 && detail.documents.every(d => d.record_origin === 'real' && d.rights !== 'synthetic'
      && noLater(d.available_at, briefing.as_of))
}
function realDerived(value: unknown): boolean {
  if (Array.isArray(value)) return value.every(realDerived)
  if (!value || typeof value !== 'object') return true
  return Object.entries(value).every(([key, item]) => key === 'record_origin' ? item === 'real'
    : key === 'redistribution_rights' || key === 'rights' ? item !== 'synthetic'
      : key === 'content_kind' ? item !== 'synthetic_text' : realDerived(item))
}
export function safeDetail(detail: EventDetailView, briefing: BriefingView, event: ArchiveView): boolean {
  return boundDetail(detail, briefing, event) && detail.candidate.rule_item.record_origin === 'real'
    && detail.claims.every(c => c.record_origin === 'real') && detail.citations.every(c => c.record_origin === 'real')
    && realDerived(detail.candidate) && realDerived(detail.claims) && realDerived(detail.citations)
}
function instantMicros(value: string): bigint | null {
  const millis = Date.parse(value)
  if (!Number.isFinite(millis)) return null
  const fraction = /\.(\d{1,6})(?:Z|[+-]\d{2}:\d{2})$/.exec(value)?.[1] || ''
  return BigInt(millis) * 1000n + BigInt(fraction.padEnd(6, '0').slice(3, 6))
}
function noLater(value: string, cutoff: string): boolean {
  const left = instantMicros(value), right = instantMicros(cutoff)
  return left !== null && right !== null && left <= right
}
export function latestAssessment(rows: ClaimAssessment[], claimKey: string, asOf: string): ClaimAssessment | undefined {
  const cutoff = instantMicros(asOf)
  if (cutoff === null) return undefined
  return rows.reduce<ClaimAssessment | undefined>((latest, row) => row.claim_key === claimKey
    && instantMicros(row.as_of) !== null && instantMicros(row.as_of)! <= cutoff
    && (!latest || instantMicros(row.as_of)! >= instantMicros(latest.as_of)!) ? row : latest, undefined)
}
export const lifecycleLabel = (state?: string) => ({ current: '当前主张', superseded: '已被更正取代（superseded）',
  historical: '历史主张（historical）', retracted: '已撤回（retracted）' } as Record<string, string>)[state || ''] || '状态未确认'

// Resolve only allowlisted complete rule-item blocks from the selected native projection.
export function projectedItem(detail: EventDetailView, delivery: DeliveryView) {
  const item = detail.candidate.rule_item
  const projection = delivery.projection
  if (!projection || !delivery.content_refs?.length) return null
  if (delivery.tier === 'radar' && projection === 'focus' || delivery.status === 'truncated' && projection !== 'minimum') return null
  const blocks = new Set<string>()
  let root: string | undefined
  for (const ref of delivery.content_refs) {
    const match = /^\/history_input\/replay\/candidates\/\d+\/rule_item\/(headline|what_happened|why_it_matters|status_text|claim_summaries\/(\d+)|risks\/(\d+)|uncertainties\/(\d+))$/.exec(ref)
    if (!match || delivery.omitted_refs?.includes(ref)) return null
    const prefix = ref.split('/rule_item/')[0]
    if (root && root !== prefix) return null
    root = prefix
    const [field, index] = match[1].split('/')
    if (index !== undefined && !(item[field as 'claim_summaries' | 'risks' | 'uncertainties'] || [])[Number(index)]) return null
    blocks.add(match[1])
  }
  if (projection !== 'focus' && blocks.has('why_it_matters') || projection === 'minimum' && blocks.has('what_happened')) return null
  return { headline: blocks.has('headline') ? item.headline : null,
    what: blocks.has('what_happened') ? item.what_happened : null,
    why: blocks.has('why_it_matters') ? item.why_it_matters : null,
    summaries: item.claim_summaries.filter((_, i) => blocks.has('claim_summaries/' + i)),
    risks: item.risks.filter((_, i) => blocks.has('risks/' + i)),
    uncertainties: item.uncertainties.filter((_, i) => blocks.has('uncertainties/' + i)),
    status: blocks.has('status_text') ? item.status_text : null }
}
export function recommendationDetail(detail: EventDetailView): boolean {
  return detail.event.native_tier !== 'hold' && detail.candidate.rule_item.tier_candidate !== 'hold'
    && detail.candidate.rule_item.record_origin === 'real'
    && detail.documents.every(d => ['permitted', 'excerpt_only'].includes(d.rights) && d.provenance === 'confirmed_feed_capture')
    && detail.documents.every(d => d.content_kind !== 'synthetic_text')
}
export const evidenceLabel = (status: string) => ({ attributed: '已保留归因 · 主张验证状态见详情', source_attributed: '仅源方声称 · 尚未独立验证',
  independently_supported: '独立来源支持 · 不等于事实真值已验证', disputed: '存在争议', unverified: '未验证',
  insufficient: '证据不足', retracted: '已撤回' } as Record<string, string>)[status] || '未验证（' + status + '）'

export function activeFeedback(rows: InteractionView[], briefingId: string, targetId: string): InteractionView[] {
  const retracted = new Set(rows.filter(r => r.kind === 'retract').map(r => r.retracts_id))
  return rows.filter(r => r.briefing_id === briefingId && r.target_id === targetId && ['ack', 'dismiss'].includes(r.kind) && !retracted.has(r.id))
}
export const personaPayload = (persona: PersonaView | null, budget: 180 | 420 | 900) => ({
  expected_persona_version: persona?.version || 0, domain_interests: persona?.domain_interests || ['AI 开发工具'],
  current_goals: persona?.current_goals || [], hard_constraints: persona?.hard_constraints || [], knowledge_known: persona?.knowledge_known || [],
  attention_budget_seconds: budget, exploration_preference: persona?.exploration_preference || 'off', locale: persona?.locale || 'zh-CN',
})
