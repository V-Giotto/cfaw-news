import { useEffect, useRef, useState } from 'react'
import { api, post, type Article, type Config, type Source, type SourceState } from './api'
import ArticleReader, { ArticleMedia } from './ArticleReader'
import { channels, channelIcons, newsTime, relativeTime } from './format'
import Icon from './Icon'

const states: Record<string, string> = { idle: '等待获取', refreshing: '获取中', ok: '获取成功', error: '获取失败' }
const sourcePriority: Record<string, number> = { 'github-blog': 0, ruanyifeng: 1, ifanr: 2, mit: 3, hn: 100 }
interface Props {
  inspect: (article: Article) => void; changed: (config: Config) => void
  openGoals: () => void; goalCount: number
}
type View = 'grid' | 'list'
function initialView(): View {
  try { return localStorage.getItem('cfaw.news.view') === 'list' ? 'list' : 'grid' } catch { return 'grid' }
}

export default function NewsLibrary({ inspect, changed, openGoals, goalCount }: Props) {
  const [articles, setArticles] = useState<Article[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [auto, setAuto] = useState<boolean | null>(null)
  const [channel, setChannel] = useState('')
  const [sourceId, setSourceId] = useState('')
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const [tick, setTick] = useState(0)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [view, setView] = useState<View>(initialView)
  const [reader, setReader] = useState<Article | null>(null)
  const [showStates, setShowStates] = useState(false)
  const feed = useRef<HTMLDivElement>(null)
  const lastOpened = useRef<HTMLButtonElement | null>(null)
  const readerPanel = useRef<HTMLElement>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => { setSearch(query); setPage(0) }, 300)
    return () => window.clearTimeout(timer)
  }, [query])
  useEffect(() => {
    let live = true
    let timer: number
    const controller = new AbortController()
    setLoading(true)
    setArticles([])
    async function sync() {
      try {
        const params = new URLSearchParams({ origin: 'feed', category: channel, source_id: sourceId, q: search, exclude_discovery: sourceId ? 'false' : 'true', limit: '41', offset: String(page * 40) })
        const [rows, src, config] = await Promise.all([
          api<Article[]>('/articles?' + params, { signal: controller.signal }),
          api<Source[]>('/sources', { signal: controller.signal }),
          api<Config>('/config', { signal: controller.signal }),
        ])
        if (live) {
          setArticles(rows); setSources(src.filter(s => s.primary).sort((a, b) => (sourcePriority[a.id] ?? 10) - (sourcePriority[b.id] ?? 10))); setAuto(config.news_auto_refresh); changed(config); setError('')
          setReader(current => { const updated = rows.find(a => a.id === current?.id); return current && updated && (current.image_url !== updated.image_url || current.image_status !== updated.image_status) ? { ...current, image_url: updated.image_url, image_status: updated.image_status, image_error: updated.image_error } : current })
        }
      } catch (err) { if (live) setError('暂时无法更新新闻。' + (err as Error).message) }
      finally { if (live) { setLoading(false); timer = window.setTimeout(sync, 5000) } }
    }
    void sync()
    return () => { live = false; controller.abort(); window.clearTimeout(timer) }
  }, [channel, sourceId, search, page, tick, changed])
  useEffect(() => { try { localStorage.setItem('cfaw.news.view', view) } catch { /* Browsing also works without local storage. */ } }, [view])
  function closeReader() { setReader(null); requestAnimationFrame(() => lastOpened.current?.focus()) }
  useEffect(() => {
    if (!reader) return
    readerPanel.current?.focus({ preventScroll: true })
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !document.querySelector('dialog[open]')) { setReader(null); requestAnimationFrame(() => lastOpened.current?.focus()) }
    }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  }, [reader?.id])

  async function refresh() {
    const ids = sources.filter(s => (!sourceId || s.id === sourceId) && (!channel || s.category === channel)).map(s => s.id)
    if (!ids.length) return
    setRefreshing(true); setError(''); setNotice('')
    try {
      const result = await post<{ results: (SourceState & { source_id: string })[] }>('/sources/refresh', { source_ids: ids })
      const ok = result.results.filter(r => r.status === 'ok')
      const added = ok.reduce((n, r) => n + (r.new_count || 0), 0)
      const failed = result.results.filter(r => r.status === 'error').length
      setNotice('已更新 ' + ok.length + ' 个来源，新增 ' + added + ' 条新闻' + (failed ? '；' + failed + ' 个暂不可用，已保留缓存' : '') + (result.results.some(r => r.status === 'refreshing') ? '；部分来源正在获取' : '') + '。')
      setTick(t => t + 1)
    } catch (err) { setError((err as Error).message) }
    finally { setRefreshing(false) }
  }
  const visible = articles.slice(0, 40)
  const selectedIndex = reader ? visible.findIndex(a => a.id === reader.id) : -1
  const total = sources.filter(s => (!channel || s.category === channel) && (sourceId ? s.id === sourceId : s.display_role !== 'discovery')).reduce((n, s) => n + s.article_count, 0)
  const selectChannel = (value: string) => { setChannel(value); setSourceId(''); setPage(0); closeReader() }
  function changePage(delta: number) { setPage(p => p + delta); closeReader(); feed.current?.scrollTo({ top: 0 }) }
  return <div className={'news-layout' + (reader ? ' reader-open' : '')}>
    <aside className="feed-rail" aria-label="新闻筛选">
      <div className="rail-title"><Icon name="library" size={16}/><span>我的阅读</span></div>
      <div className="rail-label">探索频道</div>
      <nav className="feed-channels" aria-label="新闻频道">{Object.entries(channels).map(([value, label]) => <button key={value} aria-pressed={!sourceId && channel === value} className={!sourceId && channel === value ? 'chosen' : ''} onClick={() => selectChannel(value)}><Icon name={channelIcons[value] || 'layers'} size={16}/><span>{label}</span>{!value && <span className="rail-count">{sources.filter(s => s.display_role !== 'discovery').reduce((n, s) => n + s.article_count, 0)}</span>}</button>)}</nav>
      <><div className="rail-label source-heading"><span>订阅来源</span><button className="icon-button" aria-label="查看来源状态" aria-pressed={showStates} onClick={() => setShowStates(v => !v)}><Icon name="info" size={14}/></button></div><nav className="feed-sources" aria-label="新闻来源">{sources.map(s => <button key={s.id} className={sourceId === s.id ? 'chosen' : ''} aria-pressed={sourceId === s.id} onClick={() => { setSourceId(sourceId === s.id ? '' : s.id); setChannel(''); setPage(0); closeReader() }}><span className="source-avatar">{s.label.slice(0, 1)}</span><span>{s.label}{s.display_role === 'discovery' && ' · 社区'}</span><span className={'source-dot ' + s.state.status} title={states[s.state.status]}/><small>{s.article_count}</small></button>)}</nav></>
      <select className="mobile-source-select" aria-label="筛选新闻来源" value={sourceId} onChange={e => { setSourceId(e.target.value); setChannel(''); setPage(0); closeReader() }}><option value="">全部来源</option>{sources.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select>
      <div className="rail-bottom"><div><span className="status-dot"/>{auto === null ? '同步本地状态' : auto ? '来源自动更新中' : '手动更新来源'}</div><p>好信息，连着你的下一步。</p><button onClick={openGoals}><Icon name="target" size={14}/>查看 {goalCount} 个关注<Icon name="arrow" size={14}/></button></div>
    </aside>
    <div className="feed-center">
      <div className="feed-header"><div><span className="eyebrow">YOUR DAILY PERSPECTIVE</span><h1>{search ? '搜索新闻' : sourceId ? sources.find(s => s.id === sourceId)?.label : channel ? channels[channel] + '频道' : '发现，与你有关。'}</h1><p>看见新消息，也看清下一步。</p></div><span className="feed-heading-icon"><Icon name={channelIcons[channel] || 'spark'} size={25}/></span></div>
      <div className="feed-toolbar"><div className="search-box"><Icon name="search" size={17}/><input aria-label="搜索新闻资料" placeholder="搜索新闻、话题或来源…" value={query} onChange={e => setQuery(e.target.value)}/>{query && <button className="icon-button" aria-label="清空搜索" onClick={() => setQuery('')}><Icon name="close" size={14}/></button>}</div><button className="icon-button refresh-control" title="刷新新闻" aria-label="刷新新闻" disabled={refreshing || !sources.length} onClick={refresh}><Icon name="refresh" size={18}/><span>{refreshing ? '刷新中' : '刷新'}</span></button></div>
      <div className="feed-subtoolbar"><div><span className="feed-section-title">{search ? '匹配结果' : '最新文章'}</span><span className="caption">{loading ? '读取中…' : search ? '本页 ' + visible.length + ' 篇' : total + ' 篇资料'}</span>{(sourceId || channel || search) && <button className="text-button reset-filter" onClick={() => { setQuery(''); selectChannel('') }}>清除筛选</button>}</div><div className="view-switch" role="group" aria-label="阅读布局"><button title="卡片视图" aria-label="卡片视图" aria-pressed={view === 'grid'} className={view === 'grid' ? 'chosen' : ''} onClick={() => setView('grid')}><Icon name="grid" size={16}/></button><button title="列表视图" aria-label="列表视图" aria-pressed={view === 'list'} className={view === 'list' ? 'chosen' : ''} onClick={() => setView('list')}><Icon name="list" size={17}/></button></div></div>
      <div className="feed-scroll" ref={feed}>
        {error && <div role="alert" className="alert error">{error}</div>}
        {notice && <div role="status" className="alert success">{notice}<button onClick={() => setNotice('')} aria-label="关闭刷新提示"><Icon name="close" size={16}/></button></div>}
        {showStates && <section className="source-overview"><div className="section-head"><h2>来源状态</h2><button className="icon-button" aria-label="关闭来源状态" onClick={() => setShowStates(false)}><Icon name="close" size={15}/></button></div><p className="caption">页面每 5 秒同步本地状态。来源按配置周期获取，失败时保留缓存。</p><div className="source-status-grid">{sources.map(s => <article key={s.id}><div><strong>{s.label}</strong><span className={'source-state ' + s.state.status}>{states[s.state.status]}</span></div><p>{s.article_count} 条缓存 · 最近成功 {s.state.last_success_at ? newsTime(s.state.last_success_at) : '尚无'}</p>{s.state.next_refresh_at && <p>下次计划 {newsTime(s.state.next_refresh_at)}</p>}{s.state.error && <p className="error">{s.state.error}</p>}</article>)}</div></section>}
        {loading ? <div className={'stories stories-' + view} role="status" aria-label="正在读取新闻">{[1, 2, 3, 4, 5, 6].map(n => <div className="story-skeleton" key={n}><div/><span/><span/><span/></div>)}</div> : <div className={'stories stories-' + view}>{visible.map(item => <article className={'story-card' + (reader?.id === item.id ? 'is-selected' : '')} key={item.id}><button className="story-open" aria-label={'阅读：' + item.title} aria-pressed={reader?.id === item.id} onClick={e => { lastOpened.current = e.currentTarget; setReader(item) }}><ArticleMedia article={item}/><div className="story-content"><div className="story-source"><span className="source-avatar">{item.source.slice(0, 1)}</span><span>{item.source}</span><span className="story-category">{channels[item.category || ''] || '新闻'}</span></div><h2>{item.title}</h2><p>{item.summary || '来源未提供摘要，打开条目核对来源与内容。'}</p><div className="story-footer"><span>{relativeTime(item)}</span><Icon name="arrow" size={15}/></div></div></button></article>)}</div>}
        {!loading && !articles.length && <div className="empty news-empty"><span className="empty-icon"><Icon name="search" size={28}/></span><h2>{search || sourceId || channel ? '还没有找到这条新闻' : '新闻正在路上'}</h2><p>{search || sourceId || channel ? '试试其他关键词，或切换频道与来源。' : '可以刷新来源，获取新的公开新闻。'}</p>{search || sourceId || channel ? <button className="button secondary" onClick={() => { setQuery(''); selectChannel('') }}>清除筛选</button> : <button className="button secondary" disabled={refreshing} onClick={refresh}>刷新来源</button>}</div>}
        {(page > 0 || articles.length > 40) && <div className="news-pagination"><button className="button secondary" disabled={!page} onClick={() => changePage(-1)}><Icon name="left" size={14}/>上一页</button><span>第 {page + 1} 页</span><button className="button secondary" disabled={articles.length <= 40} onClick={() => changePage(1)}>下一页<Icon name="chevron" size={14}/></button></div>}
        <div className="feed-end"><Icon name="shield" size={14}/><span>来源摘要与片段 · 做出判断前，请回到原文核对</span></div>
      </div>
    </div>
    {reader && <aside className="feed-reader" tabIndex={-1} ref={readerPanel}><ArticleReader article={reader} close={closeReader} expand={() => inspect(reader)} previous={selectedIndex > 0 ? () => setReader(visible[selectedIndex - 1]) : undefined} next={selectedIndex >= 0 && selectedIndex < visible.length - 1 ? () => setReader(visible[selectedIndex + 1]) : undefined}/></aside>}
  </div>
}
