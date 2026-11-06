import { useEffect, useRef } from 'react'
import { useIntent } from './BriefingEvidence'
import { intent, type WriteIntent } from './intelligence'

// A visible home visit is separate from card exposure and explicit knowledge.
export default function HomeVisitReceipt({ active, enabled, briefingId }: { active: boolean; enabled: boolean; briefingId: string | null }) {
  const marker = useRef<HTMLDivElement>(null)
  const session = useRef<string | null>(null)
  const jobs = useRef(new Map<string, { intent: WriteIntent; attempted: boolean }>())
  const action = useIntent()
  useEffect(() => {
    if (!active) { session.current = null; jobs.current.clear(); return }
    if (!enabled || !marker.current) return
    let visible = false
    const confirm = () => {
      if (!visible || document.hidden || action.pending) return
      session.current ||= crypto.randomUUID()
      const key = briefingId || 'empty'
      let job = jobs.current.get(key)
      if (!job) {
        job = { intent: intent('/visits', { confirmation: 'home_visible', session_key: session.current + ':' + key, briefing_id: briefingId }), attempted: false }
        jobs.current.set(key, job)
      }
      if (job.attempted) return
      job.attempted = true
      void action.run(job.intent)
    }
    const observer = new IntersectionObserver(entries => {
      visible = entries.some(e => e.isIntersecting && e.intersectionRect.width > 0 && e.intersectionRect.height > 0)
      confirm()
    })
    observer.observe(marker.current.closest('.briefing-home') || marker.current)
    document.addEventListener('visibilitychange', confirm)
    return () => { observer.disconnect(); document.removeEventListener('visibilitychange', confirm) }
  }, [active, enabled, briefingId, action.pending])
  return <div ref={marker} className="caption" style={{ minHeight: 1 }} aria-label="页面访问确认">
    {action.error && <p role="alert">访问记录未保存；不会记为已了解。{action.error}<button className="text-button" disabled={action.pending} onClick={action.retry}>重试访问记录</button></p>}
  </div>
}
