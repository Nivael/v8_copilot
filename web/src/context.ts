import type { ResearchContext } from './types'

export function contextFromSearch(search: string): ResearchContext {
  const params = new URLSearchParams(search)
  const selected = params.getAll('lens').filter(Boolean)
  return {
    ...(params.get('symbol') ? { symbol: params.get('symbol')! } : {}),
    ...(params.get('event') ? { event_id: params.get('event')! } : {}),
    ...(params.get('date') ? { event_date: params.get('date')! } : {}),
    ...(params.get('title') ? { event_title: params.get('title')! } : {}),
    ...(params.get('from') ? { time_start: params.get('from')! } : {}),
    ...(params.get('to') ? { time_end: params.get('to')! } : {}),
    ...(params.get('question') ? { active_question: params.get('question')! } : {}),
    ...(selected.length ? { selected_lenses: selected } : {}),
  }
}

export function questionSearch(context: ResearchContext, question: string): string {
  const params = new URLSearchParams()
  if (context.symbol) params.set('symbol', context.symbol)
  if (context.event_id) params.set('event', context.event_id)
  if (context.event_date) params.set('date', context.event_date)
  if (context.event_title) params.set('title', context.event_title)
  if (context.time_start) params.set('from', context.time_start)
  if (context.time_end) params.set('to', context.time_end)
  context.selected_lenses?.forEach((lens) => params.append('lens', lens))
  if (question) params.set('question', question)
  return `/?${params.toString()}`
}
