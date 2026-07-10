import { describe, expect, it } from 'vitest'
import { parseNdjsonChunk } from './api'

describe('parseNdjsonChunk', () => {
  it('preserves partial lines across chunks', () => {
    const first = parseNdjsonChunk('', '{"contract_version":"v8_copilot_api_contract_v0","request_id":"r","sequence":1,"event":"accepted","payload":{}}\n{"contract_')
    expect(first.events).toHaveLength(1)
    expect(first.events[0].event).toBe('accepted')

    const second = parseNdjsonChunk(first.remainder, 'version":"v8_copilot_api_contract_v0","request_id":"r","sequence":2,"event":"completed","payload":{}}\n')
    expect(second.events).toHaveLength(1)
    expect(second.events[0].event).toBe('completed')
    expect(second.remainder).toBe('')
  })
})
