import {describe, expect, it} from 'vitest'
import {questionLink, readContext, readNavigationFocus} from './context'

describe('ResearchContext', () => {
  it('round trips the supported event, episode, lens, date, and object scope', () => {
    const href = questionLink({
      symbol: '603398',
      selected_event: {event_id: 'e1', date: '2026-01-05', title: '重整进展'},
      selected_episode: 'restructuring_path',
      selected_lenses: ['RL-A-003'],
      date_range: {start: '2025-12-20', end: '2026-01-20'},
      object_scope: {kind: 'stock_event', ref: 'e1'},
    }, '节点前后发生了什么？')
    expect(readContext(new URL(href, 'http://local').search)).toEqual({
      symbol: '603398',
      selected_event: {event_id: 'e1', date: '2026-01-05', title: '重整进展'},
      selected_episode: 'restructuring_path',
      selected_lenses: ['RL-A-003'],
      date_range: {start: '2025-12-20', end: '2026-01-20'},
      object_scope: {kind: 'stock_event', ref: 'e1'},
      active_question: '节点前后发生了什么？',
    })
  })

  it('reads UI-only provenance and debt focus without adding it to ResearchContext', () => {
    expect(readNavigationFocus('?provenance=fixture%3A1')).toEqual({kind: 'provenance', ref: 'fixture:1'})
    expect(readNavigationFocus('?debt=D-021')).toEqual({kind: 'data_debt', ref: 'D-021'})
  })
})
