import type { Article } from './api'

export const channels: Record<string, string> = { '': '全部新闻', tech: '科技', general: '综合', science: '科研', developer: '开发者' }
export const channelIcons: Record<string, string> = { tech: 'tech', general: 'globe', science: 'science', developer: 'code' }
export const newsTime = (date: string) => new Date(date).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
export function articleTime(article: Article) {
  if (article.published_at) return `发布于 ${newsTime(article.published_at)}`
  if (article.submitted_at) return `社区提交于 ${newsTime(article.submitted_at)}`
  if (article.updated_at) return `更新于 ${newsTime(article.updated_at)} · 发布时间未知`
  return '发布时间未知'
}
export function relativeTime(article: Article) {
  const value = article.published_at || article.submitted_at
  if (!value) return articleTime(article)
  const minutes = Math.floor((Date.now() - new Date(value).getTime()) / 60000)
  const prefix = article.published_at ? '发布于' : '社区提交于'
  if (minutes >= 0 && minutes < 1) return `${prefix}刚刚`
  if (minutes >= 1 && minutes < 60) return `${prefix} ${minutes} 分钟前`
  if (minutes >= 60 && minutes < 1440) return `${prefix} ${Math.floor(minutes / 60)} 小时前`
  return articleTime(article)
}
