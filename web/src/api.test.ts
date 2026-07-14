import {afterEach, describe, expect, it, vi} from 'vitest'
import {ask, getExperiences, parseNdjson, reviewExperience} from './api'

describe('NDJSON', () => {
  afterEach(() => vi.restoreAllMocks())

  it('preserves a partial line', () => {
    const first = parseNdjson('', '{"request_id":"r","sequence":1,"event":"accepted","payload":{}}\n{"request_')
    expect(first.events[0].event).toBe('accepted')
    const second = parseNdjson(first.remainder, 'id":"r","sequence":2,"event":"completed","payload":{}}\n')
    expect(second.events[0].event).toBe('completed')
    expect(second.remainder).toBe('')
  })

  it('sends UI object scope as ResearchRequest.object, not strict ResearchContext', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(
      new ReadableStream({start(controller) { controller.close() }}),
      {status: 200},
    ))
    await ask('节点问题', {
      selected_episode: 'restructuring_path',
      object_scope: {kind: 'episode_type', ref: 'restructuring'},
    }, () => {})
    const init = fetchMock.mock.calls[0][1] as RequestInit
    const body = JSON.parse(String(init.body))
    expect(body.object).toEqual({kind: 'episode_type', ref: 'restructuring'})
    expect(body.context).toEqual({selected_episode: 'restructuring_path'})
    expect(body.context.object_scope).toBeUndefined()
  })

  it('uses explicit human review for experience acceptance', async () => {
    const fetchMock=vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({}),{status:200}))
    await reviewExperience('EXP-AAAAAAAAAAAAAAAAAAAA','accept')
    const init=fetchMock.mock.calls[0][1] as RequestInit
    expect(JSON.parse(String(init.body))).toMatchObject({action:'accept',actor_type:'human',reviewed_by:'owner'})
  })

  it('filters the experience repository by status', async () => {
    const fetchMock=vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response('[]',{status:200}))
    await getExperiences('candidate')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/experiences?status=candidate')
  })
})
