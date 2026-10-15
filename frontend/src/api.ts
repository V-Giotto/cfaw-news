export interface GoalInput {
  name: string; purpose: string; scope: string; constraints: string
  keywords: string[]; trial_requested: boolean
}
export interface Goal extends GoalInput {
  id: string; version: number; status: 'active' | 'paused'; is_demo: boolean
  created_at: string; latest_run: Run | null
}
export interface Article {
  id: string; title: string; original_title: string; source: string; source_url: string
  summary: string; published_at: string | null; captured_at: string; origin: string
  coverage_note: string; source_role: string; content_hash: string
  paragraphs: { id: string; text: string; kind: string }[]; retrieval_score?: number
  source_id?: string; category?: string; language?: string; submitted_at?: string | null
  updated_at?: string | null; first_seen_at?: string; last_seen_at?: string; original_url?: string
  image_url?: string | null
  image_status?: 'pending' | 'ready' | 'no_image' | 'unavailable'
  image_origin?: string | null
  image_error?: string | null
}
export interface Proposal { title: string; content: string; duration_minutes: number; kind: string }
export interface Judgment {
  outcome: string; change_kind: string; summary: string; next_step: string
  material_change: string; uncertainties: string[]
  citations: { article_id: string; paragraph_id: string }[]; proposal: Proposal | null
}
export interface Run {
  id: string; goal_id: string; goal_version: number; status: string; mode: string
  result: Judgment | null; error: string | null; created_at: string; finished_at: string | null
  metrics: { elapsed_ms?: number; candidate_count?: number }
  snapshot?: { goal: Goal; evidence: Article[]; corpus_count: number; basis_hash: string }
  decision?: { choice: string; reason: string } | null
}
export interface SourceState {
  status: 'idle' | 'refreshing' | 'ok' | 'error'; last_attempt_at?: string
  last_success_at?: string; next_refresh_at?: string; count?: number
  new_count?: number; updated_count?: number; error?: string | null; error_code?: string | null
}
export interface Source {
  id: string; label: string; enabled: boolean; primary: boolean; language: string
  kind: string; url: string; category: string; interval_seconds?: number
  article_count: number; state: SourceState
}
export interface Schedule { id: string; run_id: string; title: string; content: string; start: string; end: string; status: string }
export interface Config { version: string; mode: string; model: string | null; news_auto_refresh: boolean; counts: { articles: number; goals: number; runs: number } }
export interface TaskEvent { id: number; kind: string; message: string; created_at: string }

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch('/api' + path, {
    ...options, headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(typeof payload.detail === 'string' ? payload.detail : `请求未通过校验（${response.status}）`)
  }
  return response.json()
}

export const post = <T>(path: string, body: unknown = {}) => api<T>(path, { method: 'POST', body: JSON.stringify(body) })
