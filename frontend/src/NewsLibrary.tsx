import { useEffect, useState } from 'react'
import { api, post, type Article, type Config, type Source, type SourceState } from './api'
import Icon from './Icon'

const channels: Record<string, string> = { '': '全部', tech: '科技', general: '综合', science: '科研', developer: '开发者' }
const channelIcons: Record<string, string> = { tech: 'tech', general: 'globe', science: 'science', developer: 'code' }
const states: Record<string, string> = { idle: '等待获取', refreshing: '获取中', ok: '获取成功', error: '获取失败' }
export const newsTime = (date: string) => new Date(date).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
export function articleTime(article: Article) {
  if (article.published_at) return `发布于 ${newsTime(article.published_at)}`
  if (article.submitted_at) return `社区提交于 ${newsTime(article.submitted_at)}`
  if (article.updated_at) return `更新于 ${newsTime(article.updated_at)} · 发布时间未知`
  return '发布时间未知'
}
function relativeTime(article: Article) {
  const value = article.published_at || article.submitted_at
  if (!value) return articleTime(article)
  const minutes = Math.floor((Date.now() - new Date(value).getTime()) / 60000)
  const prefix = article.published_at ? '发布于' : '社区提交于'
  if (minutes >= 0 && minutes < 1) return `${prefix}刚刚`
  if (minutes >= 1 && minutes < 60) return `${prefix} ${minutes} 分钟前`
  if (minutes >= 60 && minutes < 1440) return `${prefix} ${Math.floor(minutes / 60)} 小时前`
  return articleTime(article)
}

function StoryImage({ article, featured = false }: { article: Article; featured?: boolean }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [article.image_url])
  const imageErrors: Record<string, string> = { http_401: '来源限制访问', http_403: '来源限制访问', http_404: '原文已失效', http_410: '原文已失效', http_429: '来源繁忙，稍后重试', timeout: '获取超时，待重试', connection_failed: '网络异常，待重试', dns_lookup_failed: '网络异常，待重试', dns_non_public: '来源地址无法访问', unsupported_image: '暂不支持此图片格式' }
  const imageNote = failed ? '图片加载失败' : article.image_status === 'pending' ? '配图获取中' : article.image_status === 'unavailable' ? imageErrors[article.image_error || ''] || '配图获取失败' : '原文暂无配图'
  return <div className={`story-image cover-${article.category || 'general'} ${article.image_url && !failed ? 'has-image' : 'illustrated'}`} title={!article.image_url || failed ? imageNote : undefined}>
    {article.image_url && !failed ? <img src={article.image_url} alt="" loading={featured ? 'eager' : 'lazy'} referrerPolicy="no-referrer" onError={() => setFailed(true)} /> : <div className="cover-art"><Icon name={channelIcons[article.category || ''] || 'library'} size={featured ? 86 : 38}/><span>{article.category && channels[article.category] || 'NEWS'}</span>{!featured && <span className="cover-note">{imageNote}</span>}</div>}
  </div>
}

interface Props {
  inspect: (article: Article) => void; changed: (config: Config) => void
  openGoals: () => void; openCalendar: () => void; goalCount: number; todayCount: number
}

export default function NewsLibrary({ inspect, changed, openGoals, openCalendar, goalCount, todayCount }: Props) {
  const [articles, setArticles] = useState<Article[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [auto, setAuto] = useState<boolean | null>(null)
  const [origin, setOrigin] = useState('feed')
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

  useEffect(() => {
    const timer = window.setTimeout(() => { setSearch(query); setPage(0) }, 300)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    let live = true
    let timer: number
    const controller = new AbortController()
    setLoading(true)
    async function sync() {
      try {
        const params = new URLSearchParams({ origin, category: channel, source_id: sourceId, q: search, limit: '41', offset: String(page * 40) })
        const [rows, src, config] = await Promise.all([
          api<Article[]>(`/articles?${params}`, { signal: controller.signal }),
          api<Source[]>('/sources', { signal: controller.signal }),
          api<Config>('/config', { signal: controller.signal }),
        ])
        if (live) { setArticles(rows); setSources(src.filter(s => s.primary)); setAuto(config.news_auto_refresh); changed(config); setError('') }
      } catch (err) { if (live) setError(`暂时无法更新新闻。${(err as Error).message}`) }
      finally { if (live) { setLoading(false); timer = window.setTimeout(sync, 5000) } }
    }
    void sync()
    return () => { live = false; controller.abort(); window.clearTimeout(timer) }
  }, [origin, channel, sourceId, search, page, tick, changed])

  async function refresh() {
    const ids = sources.filter(s => (!sourceId || s.id === sourceId) && (!channel || s.category === channel)).map(s => s.id)
    if (!ids.length) return
    setRefreshing(true); setError(''); setNotice('')
    try {
      const result = await post<{ results: (SourceState & { source_id: string })[] }>('/sources/refresh', { source_ids: ids })
      const ok = result.results.filter(r => r.status === 'ok')
      const added = ok.reduce((n, r) => n + (r.new_count || 0), 0)
      const failed = result.results.filter(r => r.status === 'error').length
      const running = result.results.filter(r => r.status === 'refreshing').length
      setNotice(`已更新 ${ok.length} 个来源，新增 ${added} 条新闻${failed ? `；${failed} 个暂不可用，已保留缓存` : ''}${running ? `；${running} 个正在获取` : ''}。`)
      setTick(t => t + 1)
    } catch (err) { setError((err as Error).message) }
    finally { setRefreshing(false) }
  }

  const visible = articles.slice(0, 40)
  const featured = [...visible.filter(a => a.image_url), ...visible.filter(a => !a.image_url)].slice(0, 3)
  const total = sources.filter(s => (!channel || s.category === channel) && (!sourceId || s.id === sourceId)).reduce((n, s) => n + s.article_count, 0)
  return <div className="news-library">
    <div className="news-heading"><div><span className="eyebrow">NEWS FEED</span><h1>新闻首页</h1><p>发现值得关注的消息，找到与你下一步有关的线索。</p></div></div>
    <div className="news-controls">
      <div className="search-toolbar">
        <div className="search-box"><Icon name="search" size={19}/><input aria-label="搜索新闻资料" placeholder="搜索新闻、话题或来源…" value={query} onChange={e => setQuery(e.target.value)}/>{query && <button className="icon-button" aria-label="清空搜索" onClick={() => setQuery('')}><Icon name="close" size={16}/></button>}</div>
        <select aria-label="资料类型" value={origin} onChange={e => { setOrigin(e.target.value); setChannel(''); setSourceId(''); setPage(0) }}><option value="feed">实时新闻</option><option value="archive">历史归档</option></select>
        {origin === 'feed' && <select aria-label="新闻来源" value={sourceId} onChange={e => { setSourceId(e.target.value); setPage(0) }}><option value="">全部来源</option>{sources.filter(s => !channel || s.category === channel).map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select>}
        {origin === 'feed' && <button className="refresh-news button secondary" disabled={refreshing || !sources.length} onClick={refresh}><Icon name="refresh" size={16}/><span>{refreshing ? '刷新中…' : '刷新新闻'}</span></button>}
      </div>
      <div className="browse-bar"><nav className="channel-tabs" aria-label="新闻频道">{Object.entries(channels).map(([value, label]) => <button key={value} disabled={origin === 'archive' && !!value} aria-pressed={channel === value} className={channel === value ? 'chosen' : ''} onClick={() => { setChannel(value); setSourceId(''); setPage(0) }}>{label}</button>)}</nav><div className="browse-meta"><span>{loading ? '正在读取…' : search ? `本页 ${visible.length} 条匹配` : origin === 'feed' ? `${total} 条新闻` : `${visible.length} 条历史资料`}</span>{origin === 'feed' && <span className="live-label"><span className="status-dot"/>{auto === null ? '同步中' : auto ? '自动更新' : '手动更新'}</span>}</div></div>
    </div>
    {error && <div role="alert" className="alert error">{error}</div>}
    {notice && <div role="status" className="alert success">{notice}<button onClick={() => setNotice('')} aria-label="关闭刷新提示"><Icon name="close" size={16}/></button></div>}
    {origin === 'archive' && <div className="note">历史归档保留迁移时的内容与来源，未作为今日新闻重新核实。</div>}

    {loading && page === 0 && !search && <div className="featured-section" aria-hidden="true"><div className="featured-skeleton-heading"/><div className="featured-grid">{[1, 2, 3].map(n => <div className="featured-placeholder" key={n}/>)}</div></div>}
    {!loading && featured.length > 0 && page === 0 && !search && <section className="featured-section" aria-label="新闻速览">
      <div className="section-head featured-section-head"><h2>{origin === 'archive' ? '归档回顾' : '新闻速览'}</h2><span className="caption">{origin === 'archive' ? '回到当时的来源与材料' : '来源中的近期消息'}</span></div>
      <div className="featured-grid">{featured.map(item => <button className="featured-story" key={item.id} onClick={() => inspect(item)}>
        <StoryImage article={item} featured/>
        <span className="featured-badge">{item.category && channels[item.category] || '新闻'}</span>
        <div className="featured-copy"><span className="featured-channel">{item.source}</span><h3>{item.title}</h3><span className="featured-time">{relativeTime(item)}<Icon name="arrow" size={17}/></span></div>
      </button>)}</div>
    </section>}

    <div className="news-body-layout">
    <section className="latest-section" aria-labelledby="latest-title">
      <div className="section-head news-section-head"><h2 id="latest-title">{search ? '搜索结果' : origin === 'archive' ? '历史文章' : '最新文章'}</h2><span className="caption">{loading ? '读取中' : `本页 ${visible.length} 篇`}</span></div>
      {loading ? <div className="news-skeleton" role="status" aria-label="正在读取新闻"><div/><div/><div/><div/></div> : <div className="article-grid">{visible.map(item => <article className="article-card" key={item.id}>
        <div className="source-line"><span className="source-avatar">{item.source.slice(0, 1)}</span><span>{item.source} · {relativeTime(item)}</span></div>
        <button className="article-open" onClick={() => inspect(item)}><h3>{item.title}</h3><StoryImage article={item}/><p>{item.summary || '来源未提供摘要，打开条目核对来源与内容。'}</p></button>
        <div className="article-bottom"><span className="category-tag">{origin === 'archive' ? '归档' : channels[item.category || ''] || '新闻'}</span><button className="read-story" onClick={() => inspect(item)}>查看详情<Icon name="arrow" size={15}/></button></div>
      </article>)}</div>}
      {!loading && !articles.length && <div className="empty news-empty"><Icon name="search" size={34}/><h3>{search || sourceId || channel ? '还没有找到这条新闻' : '新闻正在路上'}</h3><p>{search || sourceId || channel ? '试试其他关键词，或切换频道与来源。' : '可以刷新新闻，或稍后回来看看。'}</p>{(search || sourceId || channel) && <button className="button secondary" onClick={() => { setQuery(''); setSourceId(''); setChannel(''); setPage(0) }}>清除筛选</button>}</div>}
      {(page > 0 || articles.length > 40) && <div className="news-pagination"><button className="button secondary" disabled={!page} onClick={() => { setPage(p => p - 1); document.getElementById('latest-title')?.scrollIntoView() }}>上一页</button><span>第 {page + 1} 页</span><button className="button secondary" disabled={articles.length <= 40} onClick={() => { setPage(p => p + 1); document.getElementById('latest-title')?.scrollIntoView() }}>下一页</button></div>}
    </section>

    <aside className="news-context" aria-label="新闻辅助信息">
      <section className="workspace-shortcuts"><h2>我的工作区</h2><button className="workspace-link" onClick={openGoals}><span className="shortcut-icon"><Icon name="target" size={19}/></span><span><strong>我的关注</strong><small>{goalCount ? `${goalCount} 个关注目标` : '添加你关心的目标'}</small></span><Icon name="chevron" size={15}/></button><button className="workspace-link" onClick={openCalendar}><span className="shortcut-icon warm"><Icon name="calendar" size={19}/></span><span><strong>今日日程</strong><small>{todayCount ? `${todayCount} 项待完成安排` : '今日暂无待完成安排'}</small></span><Icon name="chevron" size={15}/></button></section>
    {origin === 'feed' && <details className="sources-panel"><summary><span><Icon name="globe" size={17}/>来源状态</span><span>{sources.filter(s => s.state.status === 'ok').length}/{sources.length} 成功<Icon name="chevron" size={13}/></span></summary><p className="caption">{auto ? '服务运行时每 10–30 分钟获取，页面每 5 秒同步。' : '自动获取已关闭，可使用上方按钮刷新。'}来源片段可能截断；HN 显示社区提交时间。</p><div className="source-status-grid">{sources.map(s => <article key={s.id} className={`source-status ${s.state.status}`}><div><strong>{s.label}</strong><span className="badge">{states[s.state.status]}</span></div><p>{s.article_count} 条缓存 · 最近成功：{s.state.last_success_at ? newsTime(s.state.last_success_at) : '尚无'}</p>{s.state.next_refresh_at && <p>下次计划：{newsTime(s.state.next_refresh_at)}</p>}{s.state.error && <p className="source-error">{s.state.error}</p>}</article>)}</div></details>}
    <div className="reading-note"><Icon name="library" size={17}/><p>摘要与来源片段帮助你发现线索。做出判断前，记得回到原文核对适用条件。</p></div>
    </aside>
    </div>
  </div>
}
