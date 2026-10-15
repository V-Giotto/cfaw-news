import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { api, post, type Article, type Config, type Goal, type GoalInput, type Run, type Schedule, type TaskEvent } from './api'
import NewsLibrary, { articleTime, newsTime } from './NewsLibrary'
import Icon from './Icon'

type Page = 'workspace' | 'library' | 'calendar' | 'history'
const terminal = new Set(['completed', 'failed', 'cancelled', 'stale'])
const statusText: Record<string, string> = { queued: '排队中', running: '检查中', completed: '已保存', failed: '检查失败', cancelled: '已取消', stale: '目标或依据已变更' }
const outcomeText: Record<string, string> = { update: '有相关进展', no_change: '继续观察', insufficient_evidence: '证据不足', needs_review: '候选待核实' }
const decisions: Record<string, string> = { watch: '继续观察', handled: '已处理', dismissed: '不采纳' }
const time = (date: string) => new Date(date).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })

function Modal({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { ref.current?.showModal(); return () => ref.current?.close() }, [])
  return <dialog ref={ref} className="modal" onCancel={close} aria-label={title}>
    <div className="modal-head"><h2>{title}</h2><button className="icon-button" onClick={close} aria-label="关闭"><Icon name="close"/></button></div>
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

function EvidenceModal({ article, close }: { article: Article; close: () => void }) {
  return <Modal title="核对证据" close={close}>
    <div className="source-line">{article.source} · {articleTime(article)}</div>
    <h3 className="evidence-title">{article.title}</h3>
    <p className="caption">{article.origin === 'archive' ? '迁移的历史归档，未在本轮联网复核。' : '本地保存的来源条目。'}采集于 {newsTime(article.captured_at)}。{article.first_seen_at && `首次发现于 ${newsTime(article.first_seen_at)}。`}</p>
    <h4>保存的摘要</h4><p className="reading">{article.summary || '来源未提供摘要'}</p>
    <h4>保存的原句 / 片段</h4>
    {article.paragraphs.length ? article.paragraphs.map(p => <blockquote key={p.id}><span className="caption">{p.id} · {({ curator_paraphrase: '归档编写文本', rss_body: 'RSS 提供的正文片段', rss_description: 'RSS 描述片段', community_text: '社区提交文本' } as Record<string, string>)[p.kind] || '归档原句'}</span><p>{p.text}</p></blockquote>) : <p className="muted">没有可用正文。摘要不等于阅读全文。</p>}
    <div className="note">{article.coverage_note || '引用可追溯不代表结论必然正确，请核对来源与适用条件。'}</div>
    {article.source_url && <a className="button secondary" href={article.source_url} target="_blank" rel="noreferrer noopener">打开原始来源<Icon name="link" size={16}/></a>}
    {article.original_url && <a className="button secondary" href={article.original_url} target="_blank" rel="noreferrer noopener">打开外链报道<Icon name="link" size={16}/></a>}
  </Modal>
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
  const [approval, setApproval] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const goal = goals.find(item => item.id === selected)
  const active = !!run && !terminal.has(run.status)
  const stale = !!goal && !!run && goal.version !== run.goal_version

  const load = useCallback(async () => {
    const [g, c, s, r] = await Promise.all([api<Goal[]>('/goals'), api<Config>('/config'), api<Schedule[]>('/schedules'), api<Run[]>('/runs')])
    setGoals(g); setConfig(c); setSchedules(s); setRuns(r)
    setSelected(old => old || g[0]?.id || '')
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
  const evidence = run?.snapshot?.evidence || []
  const titles: Record<Page, string> = { workspace: '我的关注', library: '新闻首页', calendar: '行动日程', history: '检查记录' }

  const navigate = (next: Page) => { setPage(next); window.scrollTo({ top: 0, behavior: 'instant' }) }
  const navigation = ([['library', 'home', '首页'], ['workspace', 'target', '我的关注'], ['calendar', 'calendar', '行动日程'], ['history', 'history', '检查记录']] as [Page, string, string][])

  return <div className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
    <a className="skip-link" href="#main-content">跳到主要内容</a>
    <aside className="sidebar" aria-label="工作空间侧栏">
      <a className="brand" href="#home" onClick={e => { e.preventDefault(); navigate('library') }} aria-label="CFAW News 首页"><span className="brand-monogram">c.</span><span className="brand-full">cfaw-news<small>NEWS THAT MOVES YOU</small></span></a>
      <div className="sidebar-label">工作空间</div>
      <nav className="side-nav" aria-label="主导航">{navigation.map(([key, icon, label]) => <button key={key} aria-label={label} title={label} aria-current={page === key ? 'page' : undefined} className={page === key ? 'selected' : ''} onClick={() => navigate(key)}><Icon name={icon} size={20}/><span className="nav-label">{label}</span>{key === 'workspace' && goals.length > 0 && <span className="nav-count">{goals.length}</span>}{key === 'calendar' && schedules.some(s => s.status !== 'completed') && <span className="nav-count">{schedules.filter(s => s.status !== 'completed').length}</span>}</button>)}</nav>
      <button className="sidebar-create button primary" aria-label="添加关注目标" title="添加关注目标" onClick={() => setGoalForm('new')}><Icon name="plus" size={18}/><span className="nav-label">新建关注</span></button>
      <div className="sidebar-bottom"><div className="local-workspace"><Icon name="library" size={19}/><div><strong>本机工作区</strong><p>目标、证据与决定<br/>保存在你的本机。</p></div></div><div className="sidebar-mode"><span className="status-dot"/><span>{config?.mode === 'compatible' ? `模型 · ${config.model}` : 'BM25 开发基线'}</span></div><span className="sidebar-version">CFAW NEWS · v{config?.version || '0.2.0'}</span></div>
    </aside>
    <div className="page-shell">
      <header className="workspace-header"><div className="header-location"><button className="icon-button sidebar-toggle" aria-label={sidebarCollapsed ? '展开侧栏' : '收起侧栏'} aria-expanded={!sidebarCollapsed} onClick={() => setSidebarCollapsed(value => !value)}><Icon name="panel" size={20}/></button><div className="breadcrumb"><span>工作空间</span><span className="breadcrumb-divider">/</span><strong>{titles[page]}</strong></div></div><div className="header-meta"><time dateTime={new Date().toISOString().slice(0, 10)}>{new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })}</time><span className="update-status"><span className="status-dot"/>{config?.news_auto_refresh ? '自动获取已开启' : '手动更新'}</span></div></header>
    <main className={`main page-${page}`}>
      <section className="content" id="main-content" tabIndex={-1}>
        {error && <div className="alert error" role="alert">{error}<button onClick={() => setError('')} aria-label="关闭错误"><Icon name="close" size={16}/></button></div>}
        {notice && <div className="alert success" role="status">{notice}<button onClick={() => setNotice('')} aria-label="关闭提示"><Icon name="close" size={16}/></button></div>}
        {loading ? <div className="empty">正在打开工作空间…</div> : <>
          {page !== 'library' && <section className="hero"><div><span className="eyebrow">YOUR NEXT STEP</span><h1>{titles[page]}</h1><p>{page === 'workspace' ? '让新消息，与你的下一步有关。' : page === 'calendar' ? '把确认过的下一步，留在日程里。' : '每一次判断，都有迹可循。'}</p></div>{page === 'workspace' && <button className="button primary" onClick={() => setGoalForm('new')}><Icon name="plus" size={18}/>添加关注</button>}</section>}
          {page === 'workspace' && <div className="metrics"><div><span>我的关注</span><strong>{goals.length.toString().padStart(2, '0')}</strong><small>由你确认的方向</small></div><div><span>新闻资料</span><strong>{config?.counts.articles || 0}</strong><small>保留来源与采集时间</small></div><div><span>检查记录</span><strong>{runs.length.toString().padStart(2, '0')}</strong><small>回看判断与依据</small></div></div>}

          {page === 'workspace' && <>
            <div className="section-head"><h2>我的关注<span>{goals.length}</span></h2><span className="caption">先写清目标，再判断变化</span></div>
            {goals.length ? <div className="goal-grid">{goals.map((item, index) => <button className={`goal-card ${item.id === selected ? 'active' : ''}`} key={item.id} onClick={() => { setHistoryRunId(null); setSelected(item.id) }}><div className="goal-top"><span className={`goal-symbol color-${index % 3}`}><Icon name="target" size={21}/></span><span className="badge">{item.status === 'paused' ? '已暂停' : item.is_demo ? '示例目标' : '我的目标'}</span></div><h3>{item.name}</h3><p>{item.purpose}</p><div className="goal-bottom"><span>{item.latest_run ? statusText[item.latest_run.status] : '等待首次检查'}</span><Icon name="arrow" size={17}/></div></button>)}</div> : <div className="empty">添加你的第一个目标，让新闻与你有关。</div>}
            {goal && <section className="workspace-panel">
              <div className="panel-header"><div><span className="eyebrow">当前关注 · V{goal.version}</span><h2>{goal.name}</h2></div><button className="text-button" onClick={() => setGoalForm(goal)}>编辑目标</button></div>
              <div className="goal-context"><p>{goal.constraints || '尚未补充个人条件。'}</p><div className="tags">{goal.keywords.map(word => <span key={word}>{word}</span>)}</div></div>
              <div className="check-bar"><div><strong>这一轮，发现了什么？</strong><p>{config?.mode === 'baseline' ? '基线只召回候选，语义适用性和事实变化待核实。' : '仅使用本轮证据与当前目标，不自动执行建议。'}</p></div><button className="button primary" disabled={active || starting || goal.status === 'paused'} onClick={check}><Icon name="refresh" size={16}/>{active || starting ? '正在检查…' : '检查本轮证据'}</button></div>
              {active && <div className="progress"><span className="spinner"/>{events.at(-1)?.message || '正在准备检查…'}<button className="text-button" onClick={async () => { try { await post(`/runs/${run!.id}/cancel`); setRun(await api<Run>(`/runs/${run!.id}`)); await load() } catch (err) { setError((err as Error).message) } }}>取消</button></div>}
              {run && terminal.has(run.status) && run.status !== 'completed' && <div className="note">{run.error || statusText[run.status]}。已完成的历史记录仍可在运行记录中查看。</div>}
              {stale && <div className="note">目标已编辑，下方为旧版本结果。请重新检查后再做决定或导入安排。</div>}
              {run?.result && <div className="result-layout">
                <div className="judgment"><div className="result-label"><span className="badge purple">{outcomeText[run.result.outcome]}</span><span className="caption">{run.mode === 'baseline' ? '词法基线 · 待人工核实' : '模型结果 · 已通过结构/引用校验'}</span></div><h3>目前情况</h3><p className="reading">{run.result.summary}</p><div className="next-step"><span className="eyebrow">建议下一步</span><p>{run.result.next_step}</p></div>{run.result.material_change && <p className="reading">变化说明：{run.result.material_change}</p>}<div className="uncertainties"><h4>仍需核实</h4>{run.result.uncertainties.map(item => <p key={item}><span>·</span>{item}</p>)}</div><div className="decision-bar"><span>我的决定</span>{Object.entries(decisions).map(([key, label]) => <button key={key} className={`decision ${run.decision?.choice === key ? 'chosen' : ''}`} disabled={stale} onClick={() => decide(key)}>{label}</button>)}</div>{run.result.proposal && !stale && <div className="proposal"><Icon name="calendar"/><div><strong>{run.result.proposal.title}</strong><p>{run.result.proposal.duration_minutes} 分钟 · {run.result.proposal.kind === 'verification' ? '核实任务，不代表试用推荐' : '先核实条件，再有限试用'}</p></div><button className="text-button" onClick={() => setApproval(true)}>预览并确认<Icon name="arrow" size={16}/></button></div>}</div>
                <aside className="evidence-panel"><div className="section-head"><h3>本轮候选证据</h3><span className="caption">{evidence.length} 篇</span></div><p className="caption">点击查看本轮保存的原句。引用存在不代表结论已被证实。</p>{evidence.map((item, index) => <button key={item.id} className="evidence-card" onClick={() => setArticle(item)}><span className="source-line"><span>{String(index + 1).padStart(2, '0')}</span>{item.source}</span><h4>{item.title}</h4><div className="evidence-footer"><span>{item.origin === 'archive' ? '历史归档' : '来源条目'} · {item.published_at?.slice(0, 10) || '日期未知'}</span><Icon name="arrow" size={15}/></div></button>)}{!evidence.length && <p className="muted">没有召回候选。可调整关键词或刷新来源。</p>}</aside>
              </div>}
              {!run && <div className="first-check"><div className="orbit-icon"><Icon name="target" size={30}/></div><h3>从一次有边界的检查开始</h3><p>检查本地资料中的相关候选，保留证据与尚未确认的条件。<br/>“继续观察”也可以是一个合理结果。</p></div>}
            </section>}
          </>}

          {page === 'library' && <NewsLibrary inspect={setArticle} changed={setConfig} openGoals={() => navigate('workspace')} openCalendar={() => navigate('calendar')} goalCount={goals.length} todayCount={schedules.filter(s => s.status !== 'completed' && new Date(s.start).toDateString() === new Date().toDateString()).length} />}
          {page === 'calendar' && <section className="simple-panel">{schedules.length ? schedules.map(item => <article className="schedule" key={item.id}><div className="calendar-symbol"><Icon name="calendar" size={25}/></div><div><span className="caption">{time(item.start)} — {time(item.end)}</span><h3>{item.title}</h3><p>{item.content}</p></div>{item.status === 'completed' ? <span className="badge purple">已完成</span> : <button className="button secondary" onClick={async () => { try { await post(`/schedules/${item.id}/complete`); await load() } catch (err) { setError((err as Error).message) } }}>标记完成</button>}</article>) : <div className="empty"><Icon name="calendar" size={35}/><h3>还没有需要执行的安排</h3><p>检查证据后，只有你确认的核实或试用任务才会保存到这里。</p><button className="button secondary" onClick={() => setPage('workspace')}>返回关注工作台</button></div>}</section>}
          {page === 'history' && <section className="simple-panel"><div className="history-head"><span>关注 / 时间</span><span>模式</span><span>状态</span><span>耗时</span></div>{runs.map(item => <button className="history-row" key={item.id} onClick={async () => { try { const current = await api<Run>(`/runs/${item.id}`); setHistoryRunId(item.id); setSelected(item.goal_id); setPage('workspace'); setRun(current) } catch (err) { setError((err as Error).message) } }}><span><strong>{goals.find(g => g.id === item.goal_id)?.name || '历史目标'}</strong><small>{time(item.created_at)} · V{item.goal_version}</small></span><span>{item.mode === 'baseline' ? 'BM25 基线' : '模型'}</span><span className="badge">{statusText[item.status]}</span><span>{item.metrics.elapsed_ms != null ? `${item.metrics.elapsed_ms} ms` : '—'}</span></button>)}{!runs.length && <div className="empty">尚无检查记录。完成第一轮检查后，结果会保存在这里。</div>}</section>}
          <footer className="footer"><span>CFAW NEWS · 让新消息，与你的下一步有关。</span><span>来源事实 · 模型解释 · 用户决定</span></footer>
        </>}
      </section>
    </main>
    </div>
    {goalForm && <GoalForm goal={goalForm === 'new' ? undefined : goalForm} close={() => setGoalForm(null)} saved={value => { navigate('workspace'); setHistoryRunId(null); setSelected(value.id); void load() }}/>}
    {article && <EvidenceModal article={article} close={() => setArticle(null)}/>}
    {approval && run?.result?.proposal && <ApprovalModal run={run} close={() => setApproval(false)} approved={() => { setNotice('已保存到行动日程。重复批准不会创建重复安排。'); void load() }}/>}
  </div>
}
