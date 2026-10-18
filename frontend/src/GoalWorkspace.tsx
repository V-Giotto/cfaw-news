import { useEffect, useState, type ReactNode } from 'react'
import type { Article, Config, Goal, Run, TaskEvent } from './api'
import { newsTime } from './format'
import Icon from './Icon'

const statusText: Record<string, string> = { queued: '排队中', running: '检查中', completed: '检查完成', failed: '检查失败', cancelled: '已取消', stale: '依据已变更' }
const outcomeText: Record<string, string> = { update: '有相关进展', no_change: '继续观察', insufficient_evidence: '证据不足', needs_review: '候选待核实' }
const decisions: Record<string, string> = { watch: '继续观察', handled: '已处理', dismissed: '不采纳' }
const terminal = new Set(['completed', 'failed', 'cancelled', 'stale'])
interface Props {
  goals: Goal[]; goal?: Goal; run: Run | null; config: Config | null
  active: boolean; stale: boolean; starting: boolean; changing: boolean; events: TaskEvent[]
  select: (id: string) => void; create: () => void; edit: (goal: Goal) => void
  check: () => void; cancel: () => void; decide: (choice: string) => void
  approve: () => void; inspect: (article: Article, paragraphId?: string) => void
  runDetails: ReactNode
  unfollow: () => void; refollow: () => void
}

export default function GoalWorkspace({ goals, goal, run, config, active, stale, starting, changing, events, select, create, edit, check, cancel, decide, approve, inspect, runDetails, unfollow, refollow }: Props) {
  const [allEvidence, setAllEvidence] = useState(false)
  const [showUnfollowed, setShowUnfollowed] = useState(false)
  useEffect(() => setAllEvidence(false), [run?.id])
  useEffect(() => setShowUnfollowed(goal?.status === 'unfollowed' && !goal.is_demo), [goal?.id, goal?.status])
  const following = goals.filter(item => item.status !== 'unfollowed')
  const unfollowed = goals.filter(item => item.status === 'unfollowed' && !item.is_demo)
  const visibleGoals = showUnfollowed ? unfollowed : following
  const chooseList = (unfollowedOnly: boolean) => { setShowUnfollowed(unfollowedOnly); select((unfollowedOnly ? unfollowed : following)[0]?.id || '') }
  const evidence = run?.snapshot?.evidence || []
  const citations = run?.result?.citations || []
  const result = run?.result
  return <div className="goals-layout">
    <aside className="goals-rail" aria-label="关注目标列表"><div className="goals-rail-heading"><div><span className="eyebrow">MY FOCUS</span><h1>我的关注 <span>{following.length}</span></h1></div><button className="icon-button" aria-label="添加关注目标" onClick={create}><Icon name="plus" size={19}/></button></div><p className="rail-description">从目标出发，让消息变成线索。</p><nav className="filter-tabs goal-follow-tabs" aria-label="关注状态"><button className={!showUnfollowed ? 'chosen' : ''} aria-pressed={!showUnfollowed} onClick={() => chooseList(false)}>关注中 {following.length}</button>{unfollowed.length > 0 && <button className={showUnfollowed ? 'chosen' : ''} aria-pressed={showUnfollowed} onClick={() => chooseList(true)}>已取消关注 {unfollowed.length}</button>}</nav><div className="goal-list">{visibleGoals.map((item, i) => <button key={item.id} className={'goal-list-item' + (goal?.id === item.id ? ' active' : '')} aria-pressed={goal?.id === item.id} onClick={() => select(item.id)}><div className="goal-list-top"><span className={'goal-symbol color-' + i % 3}><Icon name="target" size={17}/></span><span className="caption">{item.status === 'unfollowed' ? '已取消关注' : item.status === 'paused' ? '已暂停' : item.is_demo ? '示例目标' : '我的目标'}</span><Icon name="chevron" size={14}/></div><h2>{item.name}</h2><p>{item.purpose}</p><div className="goal-list-status"><span className={'source-dot ' + (item.latest_run?.status === 'completed' ? 'ok' : 'idle')}/>{item.latest_run ? statusText[item.latest_run.status] : '等待首次检查'}</div></button>)}</div><button className="add-goal-outline" onClick={create}><Icon name="plus" size={16}/>新建一个关注</button><div className="rail-tip"><Icon name="info" size={16}/><p>目标与条件越清楚，越容易判断一条新消息是否与你有关。</p></div></aside>
    <div className="goal-detail">{goal ? <>
      <header className="goal-detail-header"><div><span className="eyebrow">{goal.status === 'unfollowed' ? '已取消关注' : '当前关注'} · V{goal.version}</span><h2>{goal.name}</h2><p>{goal.purpose}</p></div><div className="goal-header-actions">{goal.status === 'unfollowed' ? !goal.is_demo && <button className="button secondary" disabled={changing} onClick={refollow}><Icon name="plus" size={15}/>{changing ? '恢复中…' : '恢复关注'}</button> : <><button className="button secondary" disabled={changing} onClick={() => edit(goal)}><Icon name="edit" size={15}/>编辑目标</button><button className="button secondary unfollow-button" disabled={changing} onClick={unfollow}><Icon name="close" size={15}/>{changing ? '取消中…' : '取消关注'}</button></>}</div></header>
      <details className="goal-conditions"><summary><span><Icon name="sliders" size={16}/>目标条件与检索范围</span><Icon name="chevron" size={15}/></summary><dl>{goal.scope && <div><dt>关注范围</dt><dd>{goal.scope}</dd></div>}<div><dt>条件限制</dt><dd>{goal.constraints || '尚未补充个人条件。'}</dd></div></dl><div className="tags">{goal.keywords.map(word => <span key={word}>{word}</span>)}</div></details>
      {goal.status === 'unfollowed' ? <div className="note" role="status">{goal.is_demo ? '此示例目标已清理，仅保留历史检查供回溯。可以新建自己的关注目标。' : '此目标已取消关注，不再发起检查。历史判断和已保存日程仍保留，恢复关注后可重新检查。'}</div> : <div className="check-bar"><div><strong><Icon name="spark" size={17}/>新信息，会改变下一步吗？</strong><p>{config?.mode === 'baseline' ? 'BM25 仅召回候选，适用性与事实变化仍需核实。' : '基于当前目标与本轮证据检查，行动由你决定。'}</p></div><button className="button primary" disabled={active || starting || changing || goal.status !== 'active'} onClick={check}><Icon name="refresh" size={16}/>{active || starting ? '正在检查…' : '检查本轮证据'}</button></div>}
      {active && <div className="progress" role="status"><span className="spinner"/>{events.at(-1)?.message || '正在准备检查…'}<button className="text-button" onClick={cancel}>取消检查</button></div>}
      {run && terminal.has(run.status) && run.status !== 'completed' && <div className="note" role="status">{run.error || statusText[run.status]}。已完成的历史记录仍可在检查记录中查看。</div>}
      {stale && <div className="note">{goal.status === 'unfollowed' ? '下方是取消关注前保存的历史检查，不能据此新增决定或日程。' : run?.retired_demo_evidence ? '本轮使用的演示新闻已从新闻库移除。下方仅保留历史检查快照，不能据此保存决定或导入安排；请重新检查当前新闻。' : '目标版本或状态已变化，下方为旧结果。请重新检查后再做决定或导入安排。'}</div>}
      {result && <div className="analysis-content"><div className="analysis-heading"><div><span className="analysis-icon"><Icon name="spark" size={19}/></span><h3>本轮判断</h3><span className="badge purple">{outcomeText[result.outcome]}</span></div><span className="caption">{run && newsTime(run.created_at)}</span></div><p className="analysis-disclosure">{run?.metrics.model_called === false || run?.mode === 'baseline' ? 'BM25 开发基线 · 本轮未调用模型，候选待核实' : '模型结果 · 已通过结构与引用校验，结论仍需核实'}</p>
        {evidence.length > 0 && <section className="answer-sources" aria-label="本轮候选证据"><div className="section-head"><h4><Icon name="globe" size={15}/>本轮候选证据</h4><span className="caption">{evidence.length} 篇</span></div><div className="source-card-grid">{(allEvidence ? evidence : evidence.slice(0, 3)).map((item, index) => <button key={item.id} className="answer-source-card" onClick={() => inspect(item)}><div><span className="source-avatar">{item.source.slice(0, 1)}</span><span>{item.source}</span><span className="source-number">{index + 1}</span></div><h4>{item.title}</h4><small>{item.origin === 'archive' ? '历史归档' : '来源条目'} · {item.published_at?.slice(0, 10) || (item.submitted_at ? '社区提交' : '日期未知')}</small></button>)}{evidence.length > 3 && <button className="more-sources" aria-expanded={allEvidence} onClick={() => setAllEvidence(v => !v)}><Icon name={allEvidence ? 'up' : 'layers'} size={20}/><span>{allEvidence ? '收起来源' : '查看其余 ' + (evidence.length - 3) + ' 篇'}</span></button>}</div></section>}
        <section className="judgment-summary"><h3>目前情况</h3><p className="reading">{result.summary}</p>{citations.length > 0 && <div className="inline-citations"><span>核对结果引用</span>{citations.map((ref, index) => { const source = evidence.find(item => item.id === ref.article_id); return source && <button key={ref.article_id + ':' + ref.paragraph_id + ':' + index} title={source.title + ' · ' + (ref.paragraph_id === 'summary' ? '摘要' : ref.paragraph_id)} aria-label={'引用 ' + (index + 1) + '：' + source.title} onClick={() => inspect(source, ref.paragraph_id)}><Icon name="quote" size={11}/>{index + 1}</button> })}</div>}</section>
        {result.material_change && <section className="change-note"><Icon name="history" size={17}/><div><h4>变化说明</h4><p>{result.material_change}</p></div></section>}
        <section className="next-step"><div><Icon name="arrow" size={17}/><h3>建议下一步</h3></div><p>{result.next_step}</p></section>
        {result.uncertainties.length > 0 && <section className="uncertainties"><h4><Icon name="info" size={16}/>仍需核实</h4><ul>{result.uncertainties.map(item => <li key={item}>{item}</li>)}</ul></section>}
        <div className="decision-bar"><div><strong>我的决定</strong><span>判断是线索，决定在你。</span></div><div className="decision-options">{Object.entries(decisions).map(([key, label]) => <button key={key} aria-pressed={run?.decision?.choice === key} className={'decision ' + (run?.decision?.choice === key ? 'chosen' : '')} disabled={stale} onClick={() => decide(key)}>{run?.decision?.choice === key && <Icon name="check" size={13}/ >}{label}</button>)}</div></div>
        {result.proposal && !stale && <div className="proposal"><span className="proposal-icon"><Icon name="calendar" size={21}/></span><div><strong>{result.proposal.title}</strong><p>{result.proposal.duration_minutes} 分钟 · {result.proposal.kind === 'verification' ? '有限核实安排' : '有限试用安排'} · 确认后才保存</p></div><button className="button secondary" onClick={approve}>预览并确认<Icon name="arrow" size={15}/></button></div>}
        {!evidence.length && <div className="note">本轮没有召回候选。可调整关键词或刷新来源。</div>}
      </div>}
      {!run && <div className="first-check"><span className="empty-icon"><Icon name="target" size={32}/></span><h3>{goal.status === 'unfollowed' ? '这条关注已收起。' : '让第一条线索，从这里开始。'}</h3><p>{goal.status === 'unfollowed' ? '没有保存过检查记录。恢复关注后，可以从当前新闻开始。' : <>检查本地资料中的相关候选，核对证据与适用条件。<br/>继续观察，也是一种有依据的决定。</>}</p><div className="first-check-flow"><span>目标</span><Icon name="chevron" size={14}/><span>证据</span><Icon name="chevron" size={14}/><span>判断</span><Icon name="chevron" size={14}/><span>你的决定</span></div></div>}
      {run && terminal.has(run.status) && runDetails}
    </> : <div className="empty"><span className="empty-icon"><Icon name="target" size={30}/></span><h2>你想关注什么？</h2><p>写下一个目标，把每天的新消息与你想做的事连接起来。</p><button className="button primary" onClick={create}><Icon name="plus" size={16}/>添加第一个关注</button></div>}</div>
  </div>
}
