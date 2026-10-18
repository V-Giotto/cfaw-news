import { createElement, useState, type ReactNode } from 'react'
import type { ReadingDocument, ReadingNode } from './api'
import Icon from './Icon'

const tags = new Set(['p', 'div', 'section', 'article', 'main', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'figure', 'figcaption', 'blockquote', 'pre', 'code', 'ul', 'ol', 'li', 'strong', 'b', 'em', 'i', 'br', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'sup', 'sub', 'dl', 'dt', 'dd', 's', 'del'])
function BodyImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false)
  return failed ? <span className="body-image-unavailable"><Icon name="info" size={13}/>来源图片暂不可用</span> : <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)}/>
}

export default function ReadingContent({ document }: { document: ReadingDocument }) {
  function render(node: ReadingNode, key: string): ReactNode {
    if (node.tag === 'text') return node.text || ''
    if (node.tag === 'img') return document.image_base && Number.isInteger(node.image) && node.image! >= 0 && node.image! < (document.image_count || 0) ? <BodyImage key={key} src={document.image_base + node.image} alt={node.alt || ''}/> : null
    if (!tags.has(node.tag)) return null
    const props: Record<string, unknown> = { key }
    if (node.tag === 'a' && /^https?:\/\//i.test(node.href || '')) { props.href = node.href; props.target = '_blank'; props.rel = 'noopener noreferrer' }
    return createElement(node.tag, props, ...(node.children || []).map((child, i) => render(child, key + '.' + i)))
  }
  return <div className="source-article-body">{document.nodes.map((node, i) => render(node, String(i)))}</div>
}
