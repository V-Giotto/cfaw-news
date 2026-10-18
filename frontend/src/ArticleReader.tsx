import { useEffect, useRef, useState } from 'react'
import { api, type Article, type ReadingDocument } from './api'
import { articleTime, channels, newsTime } from './format'
import Icon from './Icon'
import ReadingContent from './ReadingContent'

export function ArticleMedia({ article, eager = false }: { article: Article; eager?: boolean }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [article.id, article.image_url])
  const errors: Record<string, string> = { http_401: '来源限制访问', http_403: '来源限制访问', http_404: '原图已失效', http_410: '原图已失效', http_429: '来源繁忙', timeout: '获取超时', connection_failed: '网络异常', dns_lookup_failed: '网络异常', dns_non_public: '来源地址无法访问', unsupported_image: '暂不支持此图片格式' }
  const note = failed ? '图片加载失败' : article.image_status === 'pending' ? '配图获取中' : article.image_status === 'unavailable' ? errors[article.image_error || ''] || '配图获取失败' : '原文暂无配图'
  const github = article.source_id === 'github-blog'
  const hasImage = !!article.image_url && !failed
  return <div className={`article-media ${hasImage ? 'has-image' : 'source-brand-cover'} ${github ? 'brand-github' : 'brand-' + (article.source_id || 'general')}`} title={!hasImage ? note + '；当前为来源标识，并非文章配图' : undefined}>
    {hasImage ? <img src={article.image_url!} alt="" loading={eager ? 'eager' : 'lazy'} referrerPolicy="no-referrer" onLoad={event => { if (event.currentTarget.naturalWidth < 120 || event.currentTarget.naturalHeight < 120) setFailed(true) }} onError={() => setFailed(true)} /> : <div className="source-brand-art">
      {github ? <img className="official-github-mark" src="/source-brands/github.svg" alt="GitHub 官方标识"/> : <span className="brand-letter">{article.source_id === 'hn' ? 'Y' : article.source_id === 'mit' ? 'MIT' : article.source_id === 'ruanyifeng' ? '阮' : article.source.slice(0, 1)}</span>}
      <strong>{github ? 'GitHub Blog' : article.source}</strong><span className="brand-cover-label">{github ? '官方标识 · 来源品牌图' : '来源标识'}<span>非文章配图</span></span>
    </div>}
  </div>
}

interface Props {
  article: Article; focus?: string; close: () => void; expand?: () => void
  previous?: () => void; next?: () => void; snapshot?: boolean
}

export default function ArticleReader({ article, focus, close, expand, previous, next, snapshot = false }: Props) {
  const content = useRef<HTMLDivElement>(null)
  const [reading, setReading] = useState<ReadingDocument | null>(null)
  const [readingError, setReadingError] = useState('')
  useEffect(() => {
    setReading(null); setReadingError('')
    if (snapshot) return
    const controller = new AbortController()
    let live = true
    let timer: number
    let attempts = 0
    async function load() {
      try {
        const value = await api<ReadingDocument>('/articles/' + encodeURIComponent(article.id) + '/reading', { signal: controller.signal })
        if (!live) return
        setReading(value)
        if (value.status === 'fetching') {
          if (++attempts < 60) timer = window.setTimeout(load, 1000)
          else setReadingError('读取时间较长，可稍后重新打开，或直接访问原始来源。')
        }
      } catch (err) { if (live) setReadingError('暂时无法读取正文。' + (err as Error).message) }
    }
    void load()
    return () => { live = false; controller.abort(); window.clearTimeout(timer) }
  }, [article.id, snapshot])
  useEffect(() => {
    const target = focus ? Array.from(content.current?.querySelectorAll<HTMLElement>('[data-paragraph]') || []).find(el => el.dataset.paragraph === focus) : undefined
    // Run after a containing native dialog opens so its autofocus does not win.
    const frame = requestAnimationFrame(() => {
      if (target) { target.scrollIntoView({ block: 'center' }); target.focus({ preventScroll: true }) }
      else content.current?.scrollTo({ top: 0 })
    })
    return () => cancelAnimationFrame(frame)
  }, [article.id, focus])
  return <section className="article-reader" aria-label={snapshot ? '核对本轮证据' : '新闻阅读'}>
    <header className="reader-toolbar"><button className="reader-back" onClick={close}><Icon name="left" size={16}/><span>返回列表</span></button><div className="reader-actions">
      {(previous || next) && <><button className="icon-button" aria-label="上一篇" disabled={!previous} onClick={previous}><Icon name="up" size={17}/></button><button className="icon-button" aria-label="下一篇" disabled={!next} onClick={next}><Icon name="down" size={17}/></button><span className="toolbar-divider"/></>}
      {(article.original_url || article.source_url) && <a className="icon-button" href={article.original_url || article.source_url} target="_blank" rel="noreferrer noopener" aria-label="访问原始网页" title="访问原始网页"><Icon name="link" size={16}/></a>}
      {expand && <button className="icon-button" aria-label="展开阅读" onClick={expand}><Icon name="expand" size={17}/></button>}
      <button className="icon-button" aria-label="关闭阅读" onClick={close}><Icon name="close" size={17}/></button>
    </div></header>
    <div className="reader-scroll" ref={content}>
      <div className="reader-body">
        <div className="reader-kicker"><span className="category-tag">{article.origin === 'archive' ? '历史归档' : channels[article.category || ''] || '新闻'}</span>{snapshot && <span className="snapshot-label"><Icon name="shield" size={13}/>本轮保存的证据</span>}</div>
        <h2 className="reader-title">{article.title}</h2>
        <div className="reader-byline"><span className="source-avatar">{article.source.slice(0, 1)}</span><strong>{article.source}</strong><span>{articleTime(article)}</span></div>
        <div className="reader-cover"><ArticleMedia article={article} eager/></div>
        {!snapshot && <section className="full-reading" aria-label="来源正文">
          {reading?.status === 'ready' ? <><div className="full-reading-meta"><span><Icon name="align" size={14}/>{reading.source === 'rss' ? '订阅提供的正文' : '网页提取的正文'}</span><span>{reading.text_chars.toLocaleString('zh-CN')} 字符</span></div><ReadingContent key={article.id + ':' + reading.fetched_at} document={reading}/>{reading.truncated && <p className="note">部分内容达到阅读缓存上限，请打开原始网页查看其余内容。</p>}</> : <div className="reading-status" role="status">{!readingError && (!reading || reading.status === 'fetching') ? <><span className="spinner"/>正在读取来源正文…</> : <><Icon name="info" size={15}/>{readingError || reading?.error || '来源没有可用正文，请访问原始网页。'}</>}</div>}
        </section>}
        {(snapshot || reading?.status !== 'ready') && <section className="reader-section"><h3><Icon name="align" size={16}/>{article.origin === 'archive' ? '保存的摘要' : '来源摘要'}</h3><p tabIndex={-1} data-paragraph="summary" className={`reading ${focus === 'summary' ? 'cited-paragraph' : ''}`}>{focus === 'summary' && <span className="citation-marker">本轮引用</span>}{article.summary || '来源未提供摘要，请打开原始来源核对。'}</p></section>}
        <details className="evidence-excerpts" open={snapshot}><summary><Icon name="quote" size={16}/>保存的证据片段<span>{article.paragraphs.length}</span><Icon name="chevron" size={14}/></summary><section className="reader-section">
          {article.paragraphs.length ? article.paragraphs.map(p => <blockquote tabIndex={-1} data-paragraph={p.id} key={p.id} className={focus === p.id ? 'cited-paragraph' : ''}><div className="quote-meta">{focus === p.id && <span className="citation-marker">本轮引用</span>}<span>{({ curator_paraphrase: '归档编写文本', rss_body: 'RSS 正文片段', rss_description: 'RSS 描述片段', community_text: '社区提交文本' } as Record<string, string>)[p.kind] || '归档原句'}</span><span>{p.id}</span></div><p>{p.text}</p></blockquote>) : <p className="muted reader-empty-copy">没有保存可用正文。摘要不等于阅读全文。</p>}
        </section></details>
        <div className="reader-note"><Icon name="info" size={16}/><p>{!snapshot && reading?.status === 'ready' ? '正文来自订阅内容或网页提取，可能遗漏排版或部分内容；标注为来源标识的图片仅用于识别来源。核对重要信息时可访问原始网页。' : article.coverage_note || '来源摘要与片段帮助发现线索，做出判断前请核对原文与适用条件。'}</p></div>
        <div className="reader-links">{article.source_url && <a className="button primary" href={article.source_url} target="_blank" rel="noreferrer noopener">打开原始来源<Icon name="link" size={15}/></a>}{article.original_url && <a className="button secondary" href={article.original_url} target="_blank" rel="noreferrer noopener">外链报道<Icon name="link" size={15}/></a>}</div>
        <details className="provenance"><summary>资料与采集信息<Icon name="chevron" size={14}/></summary><dl><div><dt>资料类型</dt><dd>{article.origin === 'archive' ? '迁移的历史归档，未在本轮联网复核' : '本地保存的来源条目'}</dd></div><div><dt>采集于</dt><dd>{newsTime(article.captured_at)}</dd></div>{article.first_seen_at && <div><dt>首次发现</dt><dd>{newsTime(article.first_seen_at)}</dd></div>}{snapshot && <div><dt>核对范围</dt><dd>当前检查保存的证据快照</dd></div>}</dl></details>
      </div>
    </div>
  </section>
}
