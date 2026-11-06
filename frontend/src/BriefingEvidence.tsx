import { useEffect, useRef, useState, type ReactNode } from 'react'
import ArticleReader from './ArticleReader'
import type { Article, ArchiveView, BriefingView, EventDetailView, InteractionView, MutationView } from './api'
import { ApiError } from './api'
import { activeFeedback, boundDetail, evidenceLabel, errorText, getIntelligence, intent, latestAssessment, lifecycleLabel, observationIntent, safeDetail, safeUrl, writeIntent, type WriteIntent } from './intelligence'

export const timeText = (value: string | undefined) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '未知'

export function useIntent() {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [canDiscard, setCanDiscard] = useState(false)
  const running = useRef(false)
  const failed = useRef<{ job: WriteIntent; after?: (value: MutationView) => Promise<void> | void } | null>(null)
  async function run(job: WriteIntent, after?: (value: MutationView) => Promise<void> | void) {
    if (running.current) return
    running.current = true; setPending(true); setError(''); setCanDiscard(false); failed.current = { job, after }
    try { const receipt = await writeIntent(job); await after?.(receipt); failed.current = null }
    catch (e) { setError(errorText(e)); setCanDiscard(e instanceof ApiError && e.status === 409 && e.databaseState === 'unchanged') }
    finally { running.current = false; setPending(false) }
  }
  return { pending, error, canDiscard, discard: () => { if (canDiscard && !running.current) { failed.current = null; setError(''); setCanDiscard(false) } },
    run, retry: () => { if (failed.current) void run(failed.current.job, failed.current.after) } }
}

export function FeedbackControls({ briefing, targetId, rows, changed, enabled = true }: {
  briefing: BriefingView; targetId: string; rows: InteractionView[]; changed: () => Promise<void>; enabled?: boolean
}) {
  const action = useIntent()
  const active = activeFeedback(rows, briefing.id, targetId)
  function send(kind: 'ack' | 'dismiss' | 'retract', retractsId?: string) {
    void action.run(intent('/interactions', { briefing_id: briefing.id, expected_snapshot_version: briefing.version,
      target_id: targetId, kind, confirmation: 'explicit_user', ...(retractsId ? { retracts_id: retractsId } : {}) }), changed)
  }
  return <div className="briefing-feedback" aria-label="情报反馈" aria-busy={action.pending}>
    <div className="briefing-actions"><button className="button secondary" disabled={!enabled || action.pending || !!action.error || active.some(r => r.kind === 'ack')} onClick={() => send('ack')}>标记已了解</button>
      <button className="button secondary" disabled={!enabled || action.pending || !!action.error || active.some(r => r.kind === 'dismiss')} onClick={() => send('dismiss')}>暂不感兴趣</button>
      {active.map(row => <button className="text-button" disabled={!enabled || action.pending || !!action.error} key={row.id} onClick={() => send('retract', row.id)}>撤销{row.kind === 'ack' ? '已了解' : '不感兴趣'}</button>)}</div>
    {action.pending && <p role="status">正在保存反馈…</p>}
    {action.error && <p role="alert" className="error">{action.error} <button className="text-button" disabled={action.pending} onClick={action.retry}>重试同一操作</button>{action.canDiscard && <button className="text-button" onClick={action.discard}>放弃未提交的冲突操作</button>}</p>}
    <p className="caption">打开不等于已了解。反馈仅表达本次选择，可撤回，不证明掌握知识。</p>
  </div>
}

// Observe the actual bounded card introduction, never a hidden sentinel or mount event.
export function VisibilityReceipt({ briefing, targetId, active, ready, children }: { briefing: BriefingView; targetId: string; active: boolean; ready: boolean; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const attempted = useRef(false)
  const action = useIntent()
  const run = useRef(action.run); run.current = action.run
  useEffect(() => {
    if (!active || !ready || attempted.current || !ref.current || !('IntersectionObserver' in window)) return
    let timer: number | undefined
    let intersecting = false
    const stop = () => { window.clearTimeout(timer); timer = undefined }
    const confirm = () => {
      stop()
      if (!intersecting || document.hidden || document.querySelector('dialog[open]')) return
      timer = window.setTimeout(() => {
        const rect = ref.current?.getBoundingClientRect()
        if (!rect || document.hidden || document.querySelector('dialog[open]') || rect.bottom <= 0 || rect.top >= innerHeight) return
        attempted.current = true
        void run.current(observationIntent(briefing, targetId, 'rendered'))
        observer.disconnect()
      }, 600)
    }
    const observer = new IntersectionObserver(entries => {
      intersecting = entries.some(e => e.isIntersecting && e.intersectionRatio >= 0.6)
      if (intersecting) confirm(); else stop()
    }, { threshold: [0, 0.6, 1] })
    observer.observe(ref.current)
    document.addEventListener('visibilitychange', confirm)
    // Closing a dialog may reveal an already-intersecting card without a new IO event.
    const dialogs = new MutationObserver(confirm)
    dialogs.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['open'] })
    return () => { observer.disconnect(); dialogs.disconnect(); stop(); document.removeEventListener('visibilitychange', confirm) }
  }, [active, ready, briefing.id, briefing.version, targetId])
  return <><div ref={ref}>{children}</div>
    {action.error && <p className="error" role="alert">曝光记录未保存。{action.error}<button className="text-button" disabled={action.pending} onClick={action.retry}>重试曝光记录</button></p>}</>
}

export function EvidenceContent({ detail, hold, read }: { detail: EventDetailView; hold: boolean; read: (article: Article, paragraph?: string) => void }) {
  function articleFor(id: string): Article | undefined {
    const doc = detail.documents.find(d => d.doc_version_id === id)
    if (!doc || !safeUrl(doc.canonical_url)) return undefined
    return { id: doc.doc_version_id, title: doc.content.title, original_title: doc.content.title, source: doc.source_id,
      source_url: safeUrl(doc.canonical_url)!, summary: hold ? '' : doc.content.text_excerpt || '', published_at: doc.published_at,
      captured_at: doc.observed_at, origin: 'g4_snapshot', coverage_note: '历史不可变证据快照；外链当前内容可能已经变化。',
      source_role: 'snapshot', content_hash: doc.content_sha256,
      paragraphs: hold || ['metadata_only', 'unknown'].includes(doc.rights) ? [] : (doc.content.paragraphs || []).map((text, i) => ({ id: 'p' + (i + 1), text, kind: doc.content_kind })) }
  }
  return <>
    <div className="briefing-note">固定于 {timeText(detail.as_of)} 的 immutable snapshot · V{detail.snapshot_version}。外部原文可能更新，以此处保存的引用为准。</div>
    {hold ? <p className="briefing-note">hold / 许可受限：仅展示来源元数据与安全原因，未验证断言不作为推荐。</p> : <>
      <section><h3>证据状态</h3><p>{evidenceLabel(detail.event.evidence_status)}</p><p className="caption">规则校验不等于语义真值验证。</p></section>
      {detail.candidate.rule_item.what_happened && <section><h3>发生了什么</h3><p>{detail.candidate.rule_item.what_happened.text}</p></section>}
      {detail.candidate.rule_item.why_it_matters && <section><h3>为什么重要（推断）</h3><p>{detail.candidate.rule_item.why_it_matters.text}</p>
        {detail.candidate.rule_item.why_it_matters.limitations.map((text, i) => <p className="briefing-limitation" key={i}>{text}</p>)}</section>}
      <section><h3>完整限制与风险</h3>{detail.candidate.rule_item.risks.map((risk, i) => <p key={i}>{risk.text}</p>)}
        {detail.candidate.rule_item.uncertainties.map((text, i) => <p key={i}>{text}</p>)}</section>
      {detail.claims.map(claim => {
        const assessment = latestAssessment(detail.assessments, claim.claim_key, detail.as_of)
        return <section className="briefing-claim" key={claim.claim_key}><h3>{evidenceLabel(assessment?.verification_state || 'unverified')}</h3><p>{claim.statement}</p>
          <p className="briefing-lifecycle">{lifecycleLabel(assessment?.lifecycle)}</p>
          <p className="caption">{assessment?.lifecycle === 'retracted' || claim.marker === 'withdrawal' ? '撤回记录' : claim.marker === 'correction' ? '更正记录' : '主张记录'} · {claim.claim_key} · 独立支持数量：{assessment?.independent_support_count ?? '未提供'}（接口记录）</p>
          {[...claim.limitations, ...(assessment?.limitations || [])].map((v, i) => <p className="briefing-limitation" key={i}>{v}</p>)}</section>
      })}
      <section><h3>快照引用</h3>{detail.citations.length === 0 && <p>无可解析引用；不能据此确认事实。</p>}{detail.citations.map(citation => {
        const doc = detail.documents.find(d => d.doc_version_id === citation.doc_version_id && d.document_id === citation.document_id && d.source_id === citation.source_id)
        const index = /^p[1-9]\d*$/.test(citation.paragraph_id) ? Number(citation.paragraph_id.slice(1)) - 1 : -1
        const paragraph = doc?.content.paragraphs?.[index]
        // Native offsets count Unicode code points, not UTF-16 code units.
        const text = paragraph ? Array.from(paragraph).slice(citation.start, citation.end).join('') : undefined
        const valid = doc && !['metadata_only', 'unknown', 'synthetic'].includes(doc.rights) && text === citation.quote
          && citation.start >= 0 && citation.end > citation.start && citation.end <= Array.from(paragraph || '').length
        const article = valid ? articleFor(doc.doc_version_id) : undefined
        return <blockquote key={citation.ref_id} className="briefing-citation"><p>{valid ? citation.quote : '引用与保存版本不一致，已停止展示片段。'}</p>
          <p className="caption">{citation.source_id} · {citation.doc_version_id} · {citation.paragraph_id} [{citation.start}, {citation.end})</p>
          {article && <button className="text-button" data-read-version={article.id} data-read-paragraph={citation.paragraph_id} onClick={() => read(article, citation.paragraph_id)}>阅读此历史引用</button>}</blockquote>
      })}</section>
    </>}
    <section><h3>来源与许可元数据</h3>{detail.documents.map(doc => <div key={doc.doc_version_id} className="briefing-source"><strong>{doc.content.title}</strong>
      <p>{doc.source_id} · {doc.rights} · {doc.content_kind}</p><p className="caption">{doc.doc_version_id} · 首次观察 {timeText(doc.observed_at)} · 可用 {timeText(doc.available_at)}</p>
      {safeUrl(doc.canonical_url) && <a className="text-button" href={safeUrl(doc.canonical_url)} target="_blank" rel="noreferrer noopener">打开原始资讯（当前网页）</a>}
      {!hold && articleFor(doc.doc_version_id) && <button className="text-button" data-read-version={doc.doc_version_id} data-read-paragraph="" onClick={() => read(articleFor(doc.doc_version_id)!)}>阅读保存的文章版本</button>}</div>)}</section>
  </>
}

export default function BriefingEvidence({ briefing, event, targetId, rows, changed, close, enabled }: {
  briefing: BriefingView; event: ArchiveView; targetId: string; rows: InteractionView[]; changed: () => Promise<void>; close: () => void; enabled: boolean
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [detail, setDetail] = useState<EventDetailView | null>(null)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)
  const [reader, setReader] = useState<{ article: Article; paragraph?: string } | null>(null)
  const action = useIntent()
  const opened = useRef(false)
  const returnFocus = useRef<HTMLElement | null>(null)
  useEffect(() => {
    const panel = dialog.current
    // StrictMode replays this effect; preserve the first list trigger across that replay.
    if (!returnFocus.current && document.activeElement instanceof HTMLElement) returnFocus.current = document.activeElement
    panel?.showModal()
    return () => {
      panel?.close()
      // A replay keeps the dialog connected. Restore only after the real unmount.
      queueMicrotask(() => { if (!panel?.isConnected && returnFocus.current?.isConnected) returnFocus.current.focus() })
    }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    setError(''); setDetail(null)
    void getIntelligence<EventDetailView>('/events/detail?' + new URLSearchParams({ briefing_id: briefing.id, event_snapshot_id: event.event_snapshot_id }), controller.signal)
      .then(value => { if (!boundDetail(value, briefing, event)) throw new Error('snapshot mismatch'); setDetail(value) })
      .catch(e => { if (!controller.signal.aborted) setError(e instanceof Error && e.message === 'snapshot mismatch' ? '快照版本不一致，已停止显示。' : errorText(e)) })
    return () => controller.abort()
  }, [briefing.id, event.event_snapshot_id, tick])
  useEffect(() => {
    if (!detail || !safeDetail(detail, briefing, event) || opened.current) return
    let frame: number
    const confirm = () => { frame = requestAnimationFrame(() => {
      if (!dialog.current?.open || document.hidden) return
      if (opened.current) return
      opened.current = true
      void action.run(observationIntent(briefing, targetId, 'opened'))
    }) }
    confirm(); document.addEventListener('visibilitychange', confirm)
    return () => { cancelAnimationFrame(frame); document.removeEventListener('visibilitychange', confirm) }
  }, [detail])
  const isolated = !!detail && !safeDetail(detail, briefing, event)
  const hold = isolated || event.native_tier === 'hold' || event.rights.some(r => !['permitted', 'excerpt_only'].includes(r))
    || !!detail && (detail.candidate.rule_item.tier_candidate === 'hold' || detail.documents.some(d => !['permitted', 'excerpt_only'].includes(d.rights)
      || d.retention === 'metadata_only' || d.provenance === 'legacy_cache_metadata_observed_now'))
  function closeReader() {
    const version = reader?.article.id; const paragraph = reader?.paragraph || ''
    setReader(null)
    requestAnimationFrame(() => Array.from(dialog.current?.querySelectorAll<HTMLButtonElement>('[data-read-version]') || [])
      .find(button => button.dataset.readVersion === version && button.dataset.readParagraph === paragraph)?.focus())
  }
  return <dialog ref={dialog} className="modal briefing-dialog" aria-labelledby="briefing-evidence-title" onCancel={e => { e.preventDefault(); if (reader) closeReader(); else close() }}>
    <div className="modal-head"><h2 id="briefing-evidence-title">{reader ? '历史文章阅读' : '证据详情'}</h2><button className="button secondary" onClick={close}>关闭详情</button></div>
    {reader ? <ArticleReader article={reader.article} snapshot focus={reader.paragraph} close={closeReader}/> : <>
      <h3>{hold ? '待核实候选 · 元数据' : event.title}</h3><p className="caption">{event.reason_codes.join(' · ') || '未附加安全原因'}</p>
      {!detail && !error && <p role="status">正在读取历史证据快照…</p>}
      {error && <div role="alert" className="briefing-note error">{error}<button className="text-button" onClick={() => setTick(t => t + 1)}>重读快照</button></div>}
      {detail && <><EvidenceContent detail={detail} hold={hold} read={(article, paragraph) => setReader({ article, paragraph })}/>
        {isolated ? <p role="alert" className="briefing-note">派生证据来源不一致，已隔离主张，仅保留安全元数据；反馈不可用。</p>
          : <FeedbackControls briefing={briefing} targetId={targetId} rows={rows} changed={changed} enabled={enabled}/>}</>}
      {action.error && <p role="alert" className="error">详情已显示，打开记录未保存。{action.error}<button className="text-button" disabled={action.pending} onClick={action.retry}>重试打开记录</button></p>}
    </>}
  </dialog>
}
