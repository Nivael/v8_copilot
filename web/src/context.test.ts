import { describe, expect, it } from 'vitest'
import { contextFromSearch, questionSearch } from './context'

describe('ResearchContext URL', () => {
  it('round-trips a selected stock event into the main panel', () => {
    const href = questionSearch({
      symbol: '603398',
      event_id: 'event-1',
      event_date: '2026-01-05',
      event_title: '重整进展',
      selected_lenses: ['RL-A-003'],
    }, '这个节点前后发生了什么？')
    const context = contextFromSearch(new URL(href, 'http://localhost').search)
    expect(context).toEqual({
      symbol: '603398',
      event_id: 'event-1',
      event_date: '2026-01-05',
      event_title: '重整进展',
      selected_lenses: ['RL-A-003'],
      active_question: '这个节点前后发生了什么？',
    })
  })
})
