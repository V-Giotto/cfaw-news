import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { api, post, type Article, type Config, type Goal, type GoalInput, type Run, type Schedule, type TaskEvent } from './api'
import NewsLibrary from './NewsLibrary'
import ArticleReader from './ArticleReader'
import GoalWorkspace from './GoalWorkspace'
import { CalendarView, HistoryView } from './ActivityPages'
import Icon from './Icon'

type Page = 'workspace' | 'library' | 'calendar' | 'history'
const terminal = new Set(['completed', 'failed', 'cancelled', 'stale'])
const decisions: Record<string, string> = { watch: '继续观察', handled: '已处理', dismissed: '不采纳' }

function Modal({ title, close, children, reader = false }: { title: string; close: () => void; children: ReactNode; reader?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { ref.current?.showModal(); return () => ref.current?.close() }, [])
  return <dialog ref={ref} className={reader ? 'modal reader-dialog' : 'modal'} onCancel={close} aria-label={title}>
    {!reader && <div className="modal-head"><h2>{title}</h2><button className="icon-button" onClick={close} aria-label="关闭"><Icon name="close"/></button></div>}
    {children}
  </dialog>
}

function GoalForm({ goal, close, saved }: { goal?: Goal; close: () => void; saved: (goal: Goal) => void }) {
  const [form, setForm] = useState<GoalInput>(goal || { name: '', purpose: '', scope: '', constraints: '', keywords: [], trial_requested: false })
  const [keywords, setKeywords] = useState(goal?.keywords.join('，') || '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    const data = { name: form.name, purpose: form.purpose, scope: form.scope, constraints: form.constraints, trial_requested: form.trial_requested, keywords: keywords.split(/[,，\n]/).map(v => v.trim()).filter(Boolean) }
    try {
      const result = goal ? await api<Goal>(`/goals/${goal.id}`, { method: 'PATCH', body: JSON.stringify({ ...data, expected_version: goal.version, status: goal.status }) }) : await post<Goal>('/goals', data)
      saved(result); close()
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  return <Modal title={goal ? '编辑目标与约束' : '添加一个关注目标'} close={close}>
    <p className="muted">把真正想做的事与限制写清楚。点击确认后，才会保存为关注。</p>
    <form onSubmit={submit} className="form-stack goal-form">
      <label>关注名称<input required minLength={2} maxLength={100} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="例如：每周两小时，试一个省时工具" /></label>
      <label>关注范围<input maxLength={500} value={form.scope} onChange={e => setForm({ ...form, scope: e.target.value })} placeholder="相关产品、能力或事件" /></label>
      <label className="full-width">我想做什么<textarea required minLength={4} maxLength={800} rows={3} value={form.purpose} onChange={e => setForm({ ...form, purpose: e.target.value })} placeholder="具体任务、希望得到的帮助" /></label>
      <label className="full-width">我的条件与限制<textarea rows={2} maxLength={500} value={form.constraints} onChange={e => setForm({ ...form, constraints: e.target.value })} placeholder="设备、预算、地区、时间、明确不需要的内容" /></label>
      <label className="full-width">检索关键词<input value={keywords} onChange={e => setKeywords(e.target.value)} placeholder="用逗号分隔，例如：Mac，会议，转写" /></label>
      <label className="checkbox full-width"><input type="checkbox" checked={form.trial_requested} onChange={e => setForm({ ...form, trial_requested: e.target.checked })} />我希望有依据后，安排一次有限核实或试用</label>
      {error && <p role="alert" className="error">{error}</p>}
      <button className="button primary" disabled={busy}>{busy ? '保存中…' : '确认并保存关注'}<Icon name="check" size={17}/></button>
    </form>
  </Modal>
}

function RunDetails({ run }: { run: Run }) {
  const metrics = run.metrics
  const usage = metrics.token_usage
  const counts = (key: 'prompt_tokens' | 'completion_tokens') => usage?.length && usage.every(item => typeof item?.[key] === 'number') ? usage.reduce((sum, item) => sum + item![key]!, 0).toLocaleString('zh-CN') : '未完整返回'
  const errors: Record<string, string> = { authentication: '鉴权失败', rate_limit: '限流或额度受限', quota: '余额不足', timeout: '请求超时', connection: '连接失败', configuration: '配置错误', provider_http: '服务响应异常', output_truncated: '输出截断', content_filtered: '没有可用输出', invalid_output: '结构或引用不合格', input_too_large: '输入超出上限', cancelled: '请求已取消', internal: '内部检查失败' }
  return <details className="run-details"><summary>本轮模型与用量</summary><dl>
    <div><dt>模型调用</dt><dd>{metrics.model_called === true ? `已发起 ${metrics.request_count ?? 1} 次请求` : metrics.model_called === false ? '未调用模型' : '未记录'}</dd></div>
    {metrics.model && <div><dt>请求模型</dt><dd>{metrics.model}</dd></div>}
    {metrics.response_model && <div><dt>返回模型</dt><dd>{metrics.response_model}</dd></div>}
    <div><dt>总耗时</dt><dd>{metrics.elapsed_ms != null ? `${(metrics.elapsed_ms / 1000).toFixed(2)} 秒` : '未记录'}</dd></div>
    {metrics.model_called && <><div><dt>输入 / 输出 Token</dt><dd>{counts('prompt_tokens')} / {counts('completion_tokens')}</dd></div><div><dt>格式修正</dt><dd>{metrics.repair_count ?? 0} 次</dd></div></>}
    {metrics.error_code && <div><dt>错误类别</dt><dd>{errors[metrics.error_code] || '检查失败'}</dd></div>}
  </dl>{metrics.model_called && <p className="caption">用量仅采用服务方返回值，含格式修正请求；未返回部分保持未知。费用以服务方账单为准。</p>}</details>
}

function EvidenceModal({ article, focus, close, snapshot }: { article: Article; focus?: string; close: () => void; snapshot: boolean }) {
  return <Modal title={snapshot ? '核对本轮证据' : '阅读新闻'} close={close} reader><ArticleReader article={article} focus={focus} close={close} snapshot={snapshot}/></Modal>
}

function ApprovalModal({ run, close, approved }: { run: Run; close: () => void; approved: () => void }) {
  const proposal = run.result!.proposal!
  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1); tomorrow.setHours(20, 0, 0, 0)
  const localInput = (date: Date) => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
  const [start, setStart] = useState(localInput(tomorrow))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const date = new Date(start)
      await post(`/runs/${run.id}/approve`, { start: date.toISOString(), end: new Date(date.getTime() + proposal.duration_minutes * 60000).toISOString() })
      approved(); close()
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  return <Modal title="确认后，才会保存日程" close={close}>
    <span className="eyebrow">{proposal.kind === 'verification' ? '有限核实安排' : '有限试用安排'}</span>
    <h3>{proposal.title}</h3><p className="reading">{proposal.content}</p>
    <form className="form-stack" onSubmit={submit}>
      <label>开始时间（你的本地时区）<input type="datetime-local" required value={start} onChange={e => setStart(e.target.value)} /></label>
      <p className="muted">时长 {proposal.duration_minutes} 分钟。保存时会再次核对目标、依据与时间冲突。</p>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="button primary" disabled={busy}>{busy ? '保存中…' : '确认并导入日程'}<Icon name="calendar" size={17}/></button>
    </form>
  </Modal>
}

export default function App() {
  const [page, setPage] = useState<Page>('library')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [config, setConfig] = useState<Config | null>(null)
  const [goals, setGoals] = useState<Goal[]>([])
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [selected, setSelected] = useState('')
  const [historyRunId, setHistoryRunId] = useState<string | null>(null)
  const [run, setRun] = useState<Run | null>(null)
  const [events, setEvents] = useState<TaskEvent[]>([])
  const [goalForm, setGoalForm] = useState<Goal | 'new' | null>(null)
  const [article, setArticle] = useState<Article | null>(null)
  const [citationFocus, setCitationFocus] = useState<string | undefined>()
  const [citationSnapshot, setCitationSnapshot] = useState(false)
  const [approval, setApproval] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [changingGoal, setChangingGoal] = useState('')
  const following = goals.filter(item => item.status !== 'unfollowed')
  const historicalGoal = historyRunId && run?.goal_id === selected ? run.snapshot?.goal : undefined
  const goal = goals.find(item => item.id === selected) || (historicalGoal ? { ...historicalGoal, status: 'unfollowed' as const, latest_run: null } : undefined)
  const active = !!run && !terminal.has(run.status)
  const stale = !!run && (!!run.retired_demo_evidence || !goal || goal.status !== 'active' || goal.version !== run.goal_version)

  const load = useCallback(async () => {
    const [g, c, s, r] = await Promise.all([api<Goal[]>('/goals?include_unfollowed=true'), api<Config>('/config'), api<Schedule[]>('/schedules'), api<Run[]>('/runs')])
    setGoals(g); setConfig(c); setSchedules(s); setRuns(r)
    setSelected(old => g.some(item => item.id === old) ? old : g.find(item => item.status !== 'unfollowed')?.id || '')
  }, [])
  useEffect(() => { load().catch(err => setError(err.message)).finally(() => setLoading(false)) }, [load])
  useEffect(() => {
    let live = true
    setRun(null); setEvents([])
    const id = historyRunId || goals.find(item => item.id === selected)?.latest_run?.id
    if (id) api<Run>(`/runs/${id}`).then(value => { if (live) setRun(value) }).catch(err => setError(err.message))
    return () => { live = false }
  }, [selected, goals, historyRunId])
  useEffect(() => {
    if (!run || terminal.has(run.status)) return
    const id = run.id
    let live = true
    const update = async () => {
      try { const current = await api<Run>(`/runs/${id}`); if (live) { setRun(current); if (terminal.has(current.status)) await load() } }
      catch (err) { if (live) setError((err as Error).message) }
    }
    const stream = new EventSource(`/api/runs/${id}/events`)
    stream.onmessage = event => {
      const value: TaskEvent = JSON.parse(event.data)
      setEvents(old => old.some(e => e.id === value.id) ? old : [...old, value])
      if (terminal.has(value.kind)) { stream.close(); void update() }
    }
    // Poll persisted status as fallback; disconnecting the browser never cancels a run.
    const poll = window.setInterval(update, 1200)
    return () => { live = false; stream.close(); window.clearInterval(poll) }
  }, [run?.id, run?.status, load])

  async function check() {
    if (!goal) return
    setStarting(true); setError(''); setEvents([]); setHistoryRunId(null)
    try { setRun(await post<Run>(`/goals/${goal.id}/checks`, { expected_version: goal.version })) }
    catch (err) { setError((err as Error).message) } finally { setStarting(false) }
  }
  async function decide(choice: string) {
    if (!run) return
    try { await post(`/runs/${run.id}/decisions`, { choice }); setRun(await api<Run>(`/runs/${run.id}`)); setNotice(`已记录：${decisions[choice]}`) }
    catch (err) { setError((err as Error).message) }
  }
  async function changeFollowing(follow: boolean) {
    if (!goal || changingGoal) return
    const current = goal
    setChangingGoal(current.id); setError(''); setApproval(false)
    try {
      const updated = await post<Goal>(`/goals/${current.id}/${follow ? 'follow' : 'unfollow'}`, { expected_version: current.version })
      setHistoryRunId(null); setRun(null); setEvents([])
      if (follow) setSelected(updated.id)
      else setSelected(following.find(item => item.id !== current.id)?.id || '')
      await load()
      setNotice(follow ? `已恢复关注：${current.name}。可以重新检查当前新闻。` : `已取消关注：${current.name}。历史判断和已保存日程仍保留，可在“已取消关注”中恢复。`)
    } catch (err) { setError((err as Error).message) }
    finally { setChangingGoal('') }
  }
  const inspect = (item: Article, paragraphId?: string, snapshot = true) => { setCitationFocus(paragraphId); setCitationSnapshot(snapshot); setArticle(item) }
  const titles: Record<Page, string> = { workspace: '我的关注', library: '新闻首页', calendar: '行动日程', history: '检查记录' }

  const navigate = (next: Page) => { setPage(next); window.scrollTo({ top: 0, behavior: 'instant' }) }
  const navigation = ([['library', 'home', '新闻首页'], ['workspace', 'target', '我的关注'], ['calendar', 'calendar', '行动日程'], ['history', 'history', '检查记录']] as [Page, string, string][])

  return <div className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
    <a className="skip-link" href="#main-content">跳到主要内容</a>
    <aside className="sidebar" aria-label="工作空间侧栏">
      <a className="brand" href="#home" onClick={e => { e.preventDefault(); navigate('library') }} aria-label="CFAW News 首页"><span className="brand-monogram">c.</span><span className="brand-full">cfaw<span>.news</span><small>让新消息，与你的下一步有关。</small></span></a>
      <div className="sidebar-label">工作空间</div>
      <nav className="side-nav" aria-label="主导航">{navigation.map(([key, icon, label]) => <button key={key} aria-label={label} title={label} aria-current={page === key ? 'page' : undefined} className={page === key ? 'selected' : ''} onClick={() => navigate(key)}><Icon name={icon} size={20}/><span className="nav-label">{label}</span>{key === 'workspace' && following.length > 0 && <span className="nav-count">{following.length}</span>}{key === 'calendar' && schedules.some(s => s.status !== 'completed') && <span className="nav-count">{schedules.filter(s => s.status !== 'completed').length}</span>}</button>)}</nav>
      <button className="sidebar-create button primary" aria-label="添加关注目标" title="添加关注目标" onClick={() => setGoalForm('new')}><Icon name="plus" size={18}/><span className="nav-label">新建关注</span></button>
      <div className="sidebar-focus"><div className="sidebar-label">快捷关注</div>{following.slice(0, 3).map(item => <button key={item.id} onClick={() => { setHistoryRunId(null); setSelected(item.id); navigate('workspace') }}><span className="focus-dot"/><span>{item.name}</span></button>)}</div>
      <div className="sidebar-bottom"><div className="local-workspace"><Icon name="library" size={19}/><div><strong>本机工作区</strong><p>目标、证据与决定<br/>保存在你的本机。</p></div></div><div className="sidebar-mode"><span className="status-dot"/><span>{config?.mode === 'compatible' ? `模型 · ${config.model}` : 'BM25 开发基线'}</span></div><span className="sidebar-version">CFAW NEWS · v{config?.version || '0.2.0'}</span></div>
    </aside>
    <div className="page-shell">
      <header className="workspace-header"><div className="header-location"><button className="icon-button sidebar-toggle" aria-label={sidebarCollapsed ? '展开侧栏' : '收起侧栏'} aria-expanded={!sidebarCollapsed} onClick={() => setSidebarCollapsed(value => !value)}><Icon name="panel" size={20}/></button><div className="breadcrumb"><span>工作空间</span><span className="breadcrumb-divider">/</span><strong>{titles[page]}</strong></div></div><div className="header-meta"><time dateTime={new Date().toISOString().slice(0, 10)}>{new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })}</time><span className="update-status"><span className="status-dot"/>{config?.news_auto_refresh ? '自动获取已开启' : '手动更新'}</span></div></header>
    <main className={`main page-${page}`}>
      <section className="content" id="main-content" tabIndex={-1}>
        {error && <div className="alert error" role="alert">{error}<button onClick={() => setError('')} aria-label="关闭错误"><Icon name="close" size={16}/></button></div>}
        {notice && <div className="alert success" role="status">{notice}<button onClick={() => setNotice('')} aria-label="关闭提示"><Icon name="close" size={16}/></button></div>}
        {loading ? <div className="empty">正在打开工作空间…</div> : <>
          {(page === 'calendar' || page === 'history') && <section className="hero"><div><span className="eyebrow">YOUR NEXT STEP</span><h1>{titles[page]}</h1><p>{page === 'calendar' ? '把确认过的下一步，留在日程里。' : '每一次判断，都有迹可循。'}</p></div></section>}
          {page === 'workspace' && <GoalWorkspace goals={goals} goal={goal} run={run} config={config} active={active} stale={stale} starting={starting} changing={changingGoal === goal?.id} unfollow={() => void changeFollowing(false)} refollow={() => void changeFollowing(true)} events={events} select={id => { setHistoryRunId(null); setSelected(id) }} create={() => setGoalForm('new')} edit={setGoalForm} check={check} cancel={async () => { try { await post('/runs/' + run!.id + '/cancel'); setRun(await api<Run>('/runs/' + run!.id)); await load() } catch (err) { setError((err as Error).message) } }} decide={decide} approve={() => setApproval(true)} inspect={inspect} runDetails={run && <RunDetails run={run}/>}/>}
          {page === 'library' && <NewsLibrary inspect={item => inspect(item, undefined, false)} changed={setConfig} openGoals={() => navigate('workspace')} goalCount={following.length}/>}
          {page === 'calendar' && <CalendarView schedules={schedules} openGoals={() => navigate('workspace')} complete={async id => { try { await post('/schedules/' + id + '/complete'); await load() } catch (err) { setError((err as Error).message) } }}/>}
          {page === 'history' && <HistoryView runs={runs} goals={goals} open={async item => { try { const current = await api<Run>('/runs/' + item.id); setHistoryRunId(item.id); setSelected(item.goal_id); navigate('workspace'); setRun(current) } catch (err) { setError((err as Error).message) } }}/>}
          <footer className="footer"><span>CFAW NEWS · 让新消息，与你的下一步有关。</span><span>来源事实 · 模型解释 · 用户决定</span></footer>
        </>}
      </section>
    </main>
    </div>
    {goalForm && <GoalForm goal={goalForm === 'new' ? undefined : goalForm} close={() => setGoalForm(null)} saved={value => { navigate('workspace'); setHistoryRunId(null); setSelected(value.id); void load() }}/>}
    {article && <EvidenceModal article={article} focus={citationFocus} snapshot={citationSnapshot} close={() => setArticle(null)}/>}
    {approval && run?.result?.proposal && <ApprovalModal run={run} close={() => setApproval(false)} approved={() => { setNotice('已保存到行动日程。重复批准不会创建重复安排。'); void load() }}/>}
  </div>
}
