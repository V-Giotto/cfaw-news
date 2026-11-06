import { useCallback, useEffect, useRef, useState } from 'react'
import type { ArchiveView, BriefingView, DeliveryView, EventDetailView, InteractionView, PersonaView, RunView, SnapshotPage, Source, VisitView } from './api'
import { api, ApiError } from './api'
import BriefingEvidence, { FeedbackControls, timeText, useIntent, VisibilityReceipt } from './BriefingEvidence'
import HomeVisitReceipt from './HomeVisitReceipt'
import { changesSince, eligibleDelivery, errorText, evidenceLabel, getCardDetail, getIntelligence, intent, notFound, personaPayload,
  lifecycleLabel, projectedItem, readInteractions, readyReal, recommendationDetail, safeDetail, visitBaseline, type Status } from './intelligence'

function scopeText(value: unknown): string[] {
  if (!value || typeof value !== 'object') return []
  if ('raw_value' in value && typeof value.raw_value === 'string') return [value.raw_value]
  return Object.values(value).flatMap(scopeText)
}

function CandidateCard({ briefing, delivery, event, active, rows, changed, open }: {
  briefing: BriefingView; delivery: DeliveryView; event: ArchiveView; active: boolean; rows: InteractionView[];
  changed: () => Promise<void>; open: () => void
}) {
  const [detail, setDetail] = useState<EventDetailView | null>(null)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!active) return
    const controller = new AbortController()
    setDetail(null); setError('')
    void getCardDetail('/events/detail?' + new URLSearchParams({ briefing_id: briefing.id, event_snapshot_id: event.event_snapshot_id }), controller.signal)
      .then(value => {
        if (!safeDetail(value, briefing, event) || !recommendationDetail(value)) { setError('快照或展示资格不一致，已停止推荐；请在 Archive 核对。'); return }
        setDetail(value)
      }).catch(e => { if (!controller.signal.aborted) setError(errorText(e)) })
    return () => controller.abort()
  }, [active, briefing.id, event.event_snapshot_id, tick])
  const projection = detail ? projectedItem(detail, delivery) : null
  const item = projection && detail?.candidate.rule_item
  return <article className={'briefing-card tier-' + delivery.tier} aria-label={delivery.tier + ' 情报'}>
    <div className="briefing-card-kicker"><span>{delivery.tier === 'focus' ? 'FOCUS · 重点情报' : 'RADAR · 前沿速览'}</span><span>估算 {delivery.estimated_reading_seconds} 秒</span></div>
    {!item || !projection ? <><h3>正在核对候选资格</h3><p role={error || detail ? 'alert' : 'status'}>{error || (detail ? '缺少有效预算投影，已停止卡片展示；完整内容可在 Archive 核对。' : '正在读取当时的证据与限制…')}</p>{error && <button className="text-button" onClick={() => setTick(t => t + 1)}>重读候选</button>}</> : <>
      <VisibilityReceipt briefing={briefing} targetId={delivery.id} active={active} ready={!!item}>
        <h3 className="briefing-card-title">{projection.headline?.text || '情报候选'}</h3><p className="briefing-evidence-label">{evidenceLabel(event.evidence_status)}</p>
        <p className="caption">{[...new Set(projection.summaries.map(c => evidenceLabel(c.verification_state)))].join('；') || '未提供主张验证状态'}</p>
      </VisibilityReceipt>
      <dl className="briefing-copy">
        {projection.what && <div><dt>发生了什么</dt><dd>{projection.what.text}</dd></div>}
        {projection.why && <div><dt>为什么重要 <span className="caption">（推断）</span></dt><dd>{projection.why.text}{projection.why.limitations.map((text, i) => <p key={i}>{text}</p>)}</dd></div>}
        {projection.summaries.map(summary => <div key={summary.claim_key}><dt>来源主张 · {lifecycleLabel(summary.lifecycle)}</dt><dd>{summary.statement.text}<p>{summary.attribution} · {evidenceLabel(summary.verification_state)}</p>
          {scopeText(summary.scope).map((text, i) => <p key={'s' + i}>{text}</p>)}{summary.limitations.map((text, i) => <p key={'l' + i}>{text}</p>)}</dd></div>)}
        <div><dt>来源</dt><dd>{event.source_ids.join('、')} · {event.content_kinds.join('、')}</dd></div>
        <div><dt>限制</dt><dd>语义真值未评估；来源陈述不等于独立证实。{projection.uncertainties.join('；')}
          {projection.risks.map((risk, i) => <p key={i}>{risk.text}</p>)}</dd></div></dl>
      {projection.status && <p className="briefing-note">{projection.status}</p>}
      {delivery.status === 'truncated' && <p className="briefing-note">truncated · 预算内精简展示，完整材料可在证据详情查看。</p>}
      <div className="briefing-next"><strong>下一步可选择动作</strong><button className="button secondary" onClick={open}>核对证据与原文</button></div>
      <FeedbackControls briefing={briefing} targetId={delivery.id} rows={rows} changed={changed} enabled={active}/>
    </>}
  </article>
}

function CoverageStatus({ briefing }: { briefing: BriefingView }) {
  const c = briefing.coverage
  return <section className="briefing-coverage" aria-labelledby="coverage-heading"><h2 id="coverage-heading">来源覆盖与缺口</h2>
    <p>历史时间窗口：{timeText(c.requested_start_at)} — {timeText(c.requested_end_at)}</p>
    <p>截至 {timeText(briefing.as_of)} · 生成于 {timeText(briefing.generated_at)}</p>
    <p className={c.has_gap ? 'briefing-limitation' : ''}>{c.has_gap ? 'source gaps · 存在未覆盖或未观察时段' : '已记录的来源窗口没有报告缺口'}。覆盖观察不能证明期间没有更新。</p>
    <p>缺少来源：{c.missing_source_ids.join('、') || '无报告'} · 未观察来源：{c.unobserved_source_ids.join('、') || '无报告'}</p>
    <p>未满足受保护项：{briefing.unmet_protected_event_keys.join('、') || '无报告'}</p>
    {c.sources.map(s => <details key={s.source_id}><summary>{s.source_id} · {s.status}</summary>
      {s.segments.map((segment, i) => <p key={i}>{timeText(segment.start_at)} — {timeText(segment.end_at)} · {segment.status} · {segment.reason_codes.join('、') || '无附加原因'}</p>)}
      {s.unobserved_intervals.map((v, i) => <p key={'u' + i}>未观察：{timeText(v.start_at)} — {timeText(v.end_at)}</p>)}</details>)}
  </section>
}

export default function BriefingHome({ active, openLibrary }: { active: boolean; openLibrary: () => void }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [briefing, setBriefing] = useState<BriefingView | null>(null)
  const [persona, setPersona] = useState<PersonaView | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [budget, setBudget] = useState<180 | 420 | 900>(420)
  const [rows, setRows] = useState<InteractionView[]>([])
  const [historyComplete, setHistoryComplete] = useState(true)
  const [historyKnown, setHistoryKnown] = useState(false)
  const baseline = useRef<InteractionView | (VisitView & { kind: 'home_visible' }) | null | undefined>(undefined)
  const sessionBoundary = useRef<{ sequence: number; epoch: string } | null>(null)
  const [previous, setPrevious] = useState<BriefingView | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [historyError, setHistoryError] = useState('')
  const [pinnedId, setPinnedId] = useState('')
  const [historyId, setHistoryId] = useState('')
  const [directory, setDirectory] = useState<SnapshotPage['items']>([])
  const [directoryUpper, setDirectoryUpper] = useState<number | null>(null)
  const [directoryNext, setDirectoryNext] = useState<number | null>(null)
  const [directoryError, setDirectoryError] = useState('')
  const [directoryLoading, setDirectoryLoading] = useState(false)
  const [directoryTick, setDirectoryTick] = useState(0)
  const directoryRequest = useRef<AbortController | null>(null)
  const [search, setSearch] = useState('')
  const [selection, setSelection] = useState<{ event: ArchiveView; targetId: string } | null>(null)
  const [run, setRun] = useState<RunView | null>(null)
  const [pollError, setPollError] = useState('')
  const [pollTick, setPollTick] = useState(0)
  const [tick, setTick] = useState(0)
  const action = useIntent()
  const cancelAction = useIntent()
  const running = !!run && ['queued', 'running'].includes(run.status)
  const ready = readyReal(status)
  const historyVersion = useRef(0)

  const changed = useCallback(async () => {
    // Failed rereads never turn a confirmed write into a new intent.
    const version = ++historyVersion.current
    try {
      const result = await readInteractions()
      if (version !== historyVersion.current) return
      setRows(result.rows); setHistoryComplete(result.complete); setHistoryKnown(true); setHistoryError('')
    } catch (e) { if (version === historyVersion.current) setHistoryError('反馈可能已保存，历史重读失败。' + errorText(e)) }
  }, [])
  useEffect(() => {
    if (!active) { setSelection(null); baseline.current = undefined; sessionBoundary.current = null; setPrevious(null); return }
    const controller = new AbortController()
    setLoading(true); setError(''); setSelection(null)
    const version = ++historyVersion.current
    async function load() {
      const state = await getIntelligence<Status>('/status', controller.signal)
      if (controller.signal.aborted) return
      setStatus(state)
      if (!readyReal(state)) { setBriefing(null); return }
      if (!sessionBoundary.current) sessionBoundary.current = { sequence: state.head!.sequence, epoch: state.head!.epoch }
      if (sessionBoundary.current.epoch !== state.head!.epoch) { setBriefing(null); throw new ApiError(409, 'G4_SESSION_EPOCH_CHANGED_REOPEN_PAGE', 'unchanged') }
      const optional = async <T,>(path: string, code: string): Promise<T | null> => {
        try { return await getIntelligence<T>(path, controller.signal) } catch (e) { if (notFound(e, code)) return null; throw e }
      }
      const [snapshot, preferences] = await Promise.all([
        optional<BriefingView>(pinnedId ? '/briefings/' + encodeURIComponent(pinnedId) : '/briefings/latest', 'G4_BRIEFING_NOT_FOUND'),
        optional<PersonaView>('/persona', 'G4_PERSONA_NOT_FOUND'),
      ])
      if (controller.signal.aborted) return
      if (snapshot && (snapshot.mode !== 'real' || snapshot.schema_revision !== 'g4-pr4-briefing-v1' || !!pinnedId && snapshot.id !== pinnedId)) {
        setBriefing(null); throw new ApiError(409, 'G4_SNAPSHOT_MODE_OR_VERSION_MISMATCH', 'unchanged')
      }
      if (preferences && preferences.record_origin !== 'real') throw new ApiError(409, 'G4_PERSONA_ORIGIN_MISMATCH', 'unchanged')
      setBriefing(snapshot); setPersona(preferences); setBudget(preferences?.attention_budget_seconds || 420)
      try {
        const result = await readInteractions(controller.signal)
        if (controller.signal.aborted || version !== historyVersion.current) return
        const visit = await getIntelligence<VisitView | null>('/visits/latest?through_sequence=' + sessionBoundary.current!.sequence, controller.signal)
        if (controller.signal.aborted || version !== historyVersion.current) return
        if (visit && visit.sequence > sessionBoundary.current!.sequence) throw new Error('visit sequence exceeds page boundary')
        setRows(result.rows); setHistoryKnown(true); setHistoryComplete(result.complete); setHistoryError('')
        if (baseline.current === undefined && result.complete) baseline.current = visit ? { ...visit, kind: 'home_visible' }
          : visitBaseline(result.rows.filter(row => row.sequence <= sessionBoundary.current!.sequence)) || null
        if (baseline.current?.briefing_id) {
          try {
            const prior = await getIntelligence<BriefingView>('/briefings/' + encodeURIComponent(baseline.current.briefing_id), controller.signal)
            if (!controller.signal.aborted && prior.mode === 'real') setPrevious(prior)
          } catch (e) { if (!controller.signal.aborted) setHistoryError('上次访问的快照无法读取，不能比较变化。' + errorText(e)) }
        }
      } catch (e) { if (!controller.signal.aborted) { setHistoryKnown(false); setHistoryError('历史读取失败，不能判断上次访问。' + errorText(e)) } }
    }
    void api<Source[]>('/sources', { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setSources(value.filter(s => s.enabled)) }).catch(() => undefined)
    void load().catch(e => { if (!controller.signal.aborted) setError(errorText(e)) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [active, pinnedId, tick])

  useEffect(() => {
    directoryRequest.current?.abort()
    if (!active || !ready) { setDirectory([]); return }
    const controller = new AbortController()
    directoryRequest.current = controller
    setDirectoryLoading(true); setDirectoryError('')
    void getIntelligence<SnapshotPage>('/briefings?limit=20', controller.signal).then(page => {
      if (controller.signal.aborted) return
      if (page.stream_id !== (status && 'head' in status ? status.head?.stream_id : undefined)) throw new Error('snapshot directory stream mismatch')
      setDirectory(page.items); setDirectoryUpper(page.through_version); setDirectoryNext(page.next_before_version)
    }).catch(e => { if (!controller.signal.aborted) setDirectoryError(errorText(e)) })
      .finally(() => { if (!controller.signal.aborted) setDirectoryLoading(false) })
    return () => directoryRequest.current?.abort()
  }, [active, ready, tick, directoryTick, status && 'head' in status ? status.head?.epoch : null])

  function moreSnapshots() {
    if (directoryLoading || directoryNext === null || directoryUpper === null) return
    const controller = new AbortController()
    directoryRequest.current?.abort(); directoryRequest.current = controller
    setDirectoryLoading(true); setDirectoryError('')
    void getIntelligence<SnapshotPage>('/briefings?' + new URLSearchParams({ limit: '20',
      before_version: String(directoryNext), through_version: String(directoryUpper) }), controller.signal).then(page => {
      if (controller.signal.aborted) return
      if (page.through_version !== directoryUpper || page.stream_id !== (status && 'head' in status ? status.head?.stream_id : undefined)) throw new Error('snapshot directory changed')
      setDirectory(previous => [...new Map([...previous, ...page.items].map(item => [item.id, item])).values()])
      setDirectoryNext(page.next_before_version)
    }).catch(e => { if (!controller.signal.aborted) setDirectoryError(errorText(e)) })
      .finally(() => { if (!controller.signal.aborted) setDirectoryLoading(false) })
  }

  useEffect(() => {
    if (!active || !running || !run) return
    const controller = new AbortController()
    let timer: number
    let attempts = 0
    setPollError('')
    async function poll() {
      try {
        const current = await getIntelligence<RunView>('/runs/' + encodeURIComponent(run!.id), controller.signal)
        if (controller.signal.aborted) return
        setRun(current)
        if (!['queued', 'running'].includes(current.status)) {
          setNotice('任务状态：' + current.status + (current.reason_codes.length ? ' · ' + current.reason_codes.join('、') : ''))
          setTick(t => t + 1); return
        }
        if (++attempts >= 120) { setPollError('任务仍未结束，已暂停轮询。可继续读取任务或显式取消。'); return }
        timer = window.setTimeout(poll, 1000)
      } catch (e) { if (!controller.signal.aborted) setPollError(errorText(e)) }
    }
    void poll()
    return () => { controller.abort(); window.clearTimeout(timer) }
  }, [active, run?.id, running, pollTick])

  function generate() {
    if (!readyReal(status) || !persona) return
    setNotice('')
    void action.run(intent('/briefings', { expected_latest_version: status.head!.publication_version,
      persona_version_id: persona.id, runtime_policy_sha256: status.runtime_policy_sha256,
      visit_before_sequence: sessionBoundary.current?.sequence ?? 0,
      profile: 'focus70-radar30-v1', algorithm: 'b4' }), async receipt => {
      const current = await getIntelligence<RunView>('/runs/' + encodeURIComponent(receipt.resource_id))
      setRun(current); setNotice('已提交有界简报任务，完成前保留上一份快照。')
      if (!['queued', 'running'].includes(current.status)) setTick(t => t + 1)
    })
  }
  const visibleDeliveries = briefing?.deliveries.filter(d => eligibleDelivery(briefing, d, briefing.archive.find(a => a.event_snapshot_id === d.event_snapshot_id))) || []
  const delta = briefing && previous ? changesSince(briefing, previous) : null
  const archive = briefing?.archive.filter(a => !search || [a.title, a.event_key, ...a.source_ids, ...a.reason_codes].join(' ').toLowerCase().includes(search.toLowerCase())) || []
  return <div className="briefing-home">
    <header className="briefing-hero"><div><span className="eyebrow">YOUR INTELLIGENCE · 自主查看</span><h1>我的情报</h1><p>先看变化，再核对证据，下一步由你决定。</p></div>
      <div className="briefing-actions"><button className="button secondary" onClick={openLibrary}>打开原始资讯库</button><button className="button secondary" disabled={loading} onClick={() => setTick(t => t + 1)}>重新读取</button></div></header>
    <p className="briefing-disclosure">仅在应用内展示；未打开应用时不发送通知。原始资讯未经情报验证。
      {briefing?.history_scoring === 'validated_sqlite_prefix_native_rules_v1' ? '历史评分仅使用已确认交付和显式反馈；raw/hold 元数据反馈不视为知识。' : '此快照未应用持久化历史评分。'}</p>
    <HomeVisitReceipt active={active} enabled={ready && !loading && !error && historyKnown} briefingId={briefing?.id || null}/>
    {loading && <p role="status" className="briefing-note">正在读取情报状态与可信快照…</p>}
    {error && <p role="alert" className="briefing-note error">{error} 当前内容可能过期；请重新读取。</p>}
    {notice && <p role="status" className="briefing-note">{notice}</p>}
    {status && !ready && <section className="briefing-empty" role="status"><h2>{status.state === 'disabled' ? '情报服务尚未启用' : 'mode' in status && status.mode !== 'real' ? '开发数据已隔离' : '情报服务尚未就绪'}</h2>
      <p>{'mode' in status && status.mode === 'synthetic_development' ? 'synthetic 数据不能用于真实首页。' : '尚无可读取的真实情报，请使用原始资讯库。启用与数据库维护需要单独的显式操作。'}</p>
      <p>raw_news_only · source gaps：当前没有可确认的情报覆盖。{'code' in status && typeof status.code === 'string' ? status.code : ''}</p></section>}
    <section className="briefing-preferences" aria-labelledby="budget-heading"><div><h2 id="budget-heading">阅读预算 <span>估算</span></h2><p>阅读时间未经校准；切换后保存偏好，再手动生成新简报。</p>
      <label>预算 <select aria-label="估算阅读预算" value={budget} disabled={!ready || loading || !!error || action.pending || running || !!action.error} onChange={e => setBudget(Number(e.target.value) as 180 | 420 | 900)}>{[180, 420, 900].map(value => <option value={value} key={value}>{value} 秒（估算）</option>)}</select></label></div>
      <div><p>关注范围：{persona?.domain_interests.join('、') || '尚未保存；可使用通用 AI 开发工具偏好'}</p><p>已启用来源：{sources.map(s => s.label).join('、') || '无可确认来源'}</p>
        <button className="button secondary" disabled={!ready || loading || !!error || action.pending || running || !!action.error} onClick={() => void action.run(intent('/persona', personaPayload(persona, budget)), () => { setNotice('偏好已保存。可手动生成新的简报。'); setTick(t => t + 1) })}>{action.pending ? '保存或提交中…' : persona ? '保存预算' : '保存通用偏好'}</button>
        <button className="button primary" disabled={!ready || !persona || !status || !('worker_available' in status) || !status.worker_available || running || action.pending || loading || !!error || !!action.error || persona.attention_budget_seconds !== budget || !!pinnedId}
          onClick={generate}>生成简报</button></div>
    </section>
    {action.error && <p role="alert" className="briefing-note error">{action.error}<button className="text-button" disabled={action.pending} onClick={action.retry}>幂等重试同一操作</button><span> 如为版本冲突，请先重新读取。</span>{action.canDiscard && <button className="text-button" onClick={() => { action.discard(); setTick(t => t + 1) }}>放弃未提交的冲突操作并重读</button>}</p>}
    {run && <section className="briefing-note" aria-label="简报任务状态"><p role="status">任务 {run.id} · {run.status} · {run.reason_codes.join('、')}</p>
      {running && <button className="button secondary" disabled={cancelAction.pending || !!cancelAction.error} onClick={() => void cancelAction.run(intent('/runs/' + encodeURIComponent(run.id) + '/cancel', { expected_run_version: run.version }), async () => {
        const current = await getIntelligence<RunView>('/runs/' + encodeURIComponent(run.id)); setRun(current); setNotice('取消请求已确认，上一份快照保留。'); setTick(t => t + 1)
      })}>{cancelAction.pending ? '取消中…' : '取消生成'}</button>}
      {pollError && <p role="alert">{pollError}<button className="text-button" onClick={() => setPollTick(t => t + 1)}>继续读取任务</button></p>}
      {cancelAction.error && <p role="alert">{cancelAction.error}<button className="text-button" disabled={cancelAction.pending} onClick={cancelAction.retry}>重试取消</button>{cancelAction.canDiscard && <button className="text-button" onClick={() => { cancelAction.discard(); setPollTick(t => t + 1) }}>放弃冲突并重读任务</button>}</p>}</section>}
    <section className="briefing-revisit" aria-labelledby="revisit-heading"><h2 id="revisit-heading">自上次访问以来</h2>
      {briefing?.visit_window && <p>生成窗口：{timeText(briefing.visit_window.start_at)} 至 {timeText(briefing.visit_window.end_at)} · 依据 {{
        explicit_request: '用户指定', last_confirmed_interaction: '上次已确认操作（兼容旧记录）', last_confirmed_home_visit: '上次已确认的页面访问',
        first_visit_default: '暂无确认访问，使用一天默认窗口', clamped_last_visit: '上次确认访问，限长 30 天',
      }[briefing.visit_window.basis]}
        {briefing.visit_window.basis === 'clamped_last_visit' ? '（上次访问早于 30 天，窗口已明确限长，不能推断更早覆盖）' : ''}</p>}
      {historyError && <p role="alert" className="error">{historyError}<button className="text-button" onClick={() => setTick(t => t + 1)}>重读历史</button></p>}
      {!historyKnown || !historyComplete ? <p>访问历史未知或超过读取上限，不能可靠比较；included 不视为看过。</p>
        : !baseline.current ? <p>没有已确认的上次访问。简报被收录（included）不等于你看过。</p> : <><p>上次可观察访问：{timeText(baseline.current.available_at)}（{baseline.current.kind}）。打开不等于知道。</p>
          {delta && !pinnedId ? <p>与该次快照比较：新增候选 {delta.added} · 修订变化 {delta.changed} · 相同修订 {delta.same} · 退出当前候选 {delta.absent}。修订变化不直接证明实质变化；退出不表示事实撤回。</p> : <p>当前为历史快照或缺少可比较快照，无法计算本次增量。</p>}</>}
    </section>
    {pinnedId && <div className="briefing-note" role="status">{briefing?.id === pinnedId ? '正在查看历史快照 ' + pinnedId + '，截至 ' + timeText(briefing.as_of) : '请求读取快照 ' + pinnedId + '；尚未切换，当前仍保留 ' + (briefing?.id || '空态')}。<button className="text-button" onClick={() => setPinnedId('')}>返回最新简报</button></div>}
    {briefing ? <>
      <div className="briefing-snapshot-meta">{briefing.evidence_status} · V{briefing.version} · 截至 {timeText(briefing.as_of)} · 生成于 {timeText(briefing.generated_at)}<br/>简报 {briefing.id} · 估算预算 {briefing.budget_diagnostics?.budget_seconds ?? '未计算'} 秒 · {briefing.reason_codes.join('、')}
        <p aria-label="快照估算预算">{briefing.budget_diagnostics ? `估算已用 ${briefing.budget_diagnostics.used_seconds} 秒 / 剩余 ${briefing.budget_diagnostics.unused_seconds} 秒` : '估算已用 / 剩余：未计算'}</p></div>
      <nav className="briefing-tier-nav" aria-label="情报层级"><a href="#focus-tier">Focus {visibleDeliveries.filter(d => d.tier === 'focus').length}</a><a href="#radar-tier">Radar {visibleDeliveries.filter(d => d.tier === 'radar').length}</a><a href="#archive-tier">Archive {briefing.archive.length}</a></nav>
      {(['focus', 'radar'] as const).map(tier => <section key={tier} id={tier + '-tier'} className="briefing-tier"><h2>{tier === 'focus' ? 'Focus · 重点情报' : 'Radar · 前沿速览'}</h2>
        {visibleDeliveries.some(d => d.tier === tier) ? <div className={tier === 'focus' ? 'briefing-focus-grid' : 'briefing-radar-list'}>{visibleDeliveries.filter(d => d.tier === tier).sort((a, b) => a.ordinal - b.ordinal).map(d => {
          const event = briefing.archive.find(a => a.event_snapshot_id === d.event_snapshot_id)!
          return <CandidateCard key={briefing.id + d.id} briefing={briefing} delivery={d} event={event} active={active && ready && !loading && !error} rows={rows} changed={changed} open={() => setSelection({ event, targetId: d.id })}/>
        })}</div> : <div className="briefing-empty"><h3>暂无经过证据校验的{tier === 'focus' ? '重点情报' : '速览'}</h3><p>{briefing.evidence_status === 'raw_news_only' ? 'raw_news_only · 当前只适合阅读原始资讯。' : '没有真实 eligible 候选，未填充演示内容。'}可在 Archive 核对原因。</p></div>}</section>)}
      <CoverageStatus briefing={briefing}/>
      <section className="briefing-tier" id="archive-tier"><div className="briefing-section-head"><div><h2>Archive · 完整候选</h2><p className="caption">共 {briefing.archive.length} 项，显示 {archive.length} 项；保留 excluded / truncated / hold 及未展示原因。</p></div><label>搜索候选<input aria-label="搜索 Archive" value={search} onChange={e => setSearch(e.target.value)} placeholder="来源、事件或原因"/></label></div>
        {!archive.length && <p className="briefing-empty">{search ? '没有匹配的候选。' : '这份快照没有候选。'}</p>}
        <div className="briefing-archive">{archive.map(event => {
          const d = briefing.deliveries.find(d => d.event_snapshot_id === event.event_snapshot_id)
          const diagnostic = briefing.budget_diagnostics
          const hold = event.native_tier === 'hold' || event.rights.some(r => !['permitted', 'excerpt_only'].includes(r))
          const state = hold ? 'hold' : diagnostic?.excluded_event_keys.includes(event.event_key) ? 'excluded' : d?.status || '未纳入本次展示'
          return <article key={event.id}><div><span className="badge">{state}</span><h3>{hold ? '待核实候选 · 仅许可元数据' : event.title}</h3>
            <p>{event.source_ids.join('、')} · {event.rights.join('、')} · {evidenceLabel(event.evidence_status)}</p>
            <p className="caption">事件 {event.event_key} · {event.event_snapshot_id}</p><p className="briefing-limitation">安全/展示原因：{[...new Set([...event.reason_codes, ...(d?.reason_codes || [])])].join('、') || (hold ? '证据或许可不足，仅元数据' : '未附加原因；不代表获得推荐资格')}</p></div>
            <button className="button secondary" onClick={() => setSelection({ event, targetId: d?.id || event.id })}>查看{hold ? '许可元数据' : '候选证据'}</button></article>
        })}</div>
      </section>
    </> : !loading && ready && <section className="briefing-empty"><h2>暂无真实情报快照</h2><p>raw_news_only · 尚无合格 Focus / Radar。source gaps：尚无可确认的覆盖窗口。保存偏好后可手动生成，或进入原始资讯库。</p></section>}
    <section className="briefing-history"><h2>简报快照历史</h2><p>按当前数据流分页列出已生成的不可变快照，包括无交互的 raw 简报。存在于目录不代表已看过或已了解。</p>
      {directoryError && <p role="alert">历史目录读取失败：{directoryError}<button className="text-button" onClick={() => setDirectoryTick(t => t + 1)}>重读目录</button></p>}
      {directoryLoading && <p role="status">正在读取快照目录…</p>}
      <div className="briefing-actions">{directory.map(item => <button className="button secondary" key={item.id} disabled={!ready || loading || !!error}
        aria-label={'打开历史简报 V' + item.version} onClick={() => setPinnedId(item.id)}>{item.id === briefing?.id ? '当前 · ' : ''}V{item.version} · {timeText(item.generated_at)} · {item.evidence_status}<br/>{item.id}</button>)}</div>
      {!directory.length && !directoryLoading && !directoryError && <p>暂无可列出的快照。</p>}
      {directoryNext !== null && <button className="button secondary" disabled={directoryLoading} onClick={moreSnapshots}>加载更早快照</button>}
      <form className="briefing-actions" onSubmit={e => { e.preventDefault(); if (historyId.trim()) setPinnedId(historyId.trim()) }}><label>历史快照 ID<input maxLength={512} required value={historyId} onChange={e => setHistoryId(e.target.value)}/></label><button className="button secondary" disabled={!ready || loading}>打开历史快照</button></form>
    </section>
    {selection && briefing && active && <BriefingEvidence key={briefing.id + selection.targetId} briefing={briefing} event={selection.event} targetId={selection.targetId}
      rows={rows} changed={changed} close={() => setSelection(null)} enabled={ready && !error}/>} 
  </div>
}
