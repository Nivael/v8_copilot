import type { ResearchContext, StockDossier, StreamEvent } from './types'

export function parseNdjsonChunk(
  buffer: string,
  chunk: string,
): { events: StreamEvent[]; remainder: string } {
  const lines = `${buffer}${chunk}`.split('\n')
  const remainder = lines.pop() ?? ''
  const events = lines
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as StreamEvent)
  return { events, remainder }
}

export async function streamAnswer(
  question: string,
  context: ResearchContext,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/v1/answers/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contract_version: 'v8_copilot_api_contract_v0',
      question,
      object: context.symbol
        ? { kind: 'stock', ref: context.symbol, display_name: null }
        : null,
      context: Object.keys(context).length ? context : null,
      llm_mode: 'auto',
    }),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`研究服务返回 ${response.status}`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    const parsed = parseNdjsonChunk(buffer, decoder.decode(value, { stream: true }))
    buffer = parsed.remainder
    parsed.events.forEach(onEvent)
  }
  const tail = buffer.trim()
  if (tail) onEvent(JSON.parse(tail) as StreamEvent)
}

export async function fetchDossier(symbol: string, signal?: AbortSignal): Promise<StockDossier> {
  const response = await fetch(`/api/v1/stocks/${encodeURIComponent(symbol)}/dossier`, { signal })
  if (!response.ok) throw new Error(`个股证据服务返回 ${response.status}`)
  return response.json() as Promise<StockDossier>
}
