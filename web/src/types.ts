export type EventName =
  | 'accepted'
  | 'interpreted'
  | 'routed'
  | 'answer_card'
  | 'claim_block'
  | 'degraded'
  | 'completed'
  | 'error'

export interface ResearchContext {
  symbol?: string
  event_id?: string
  event_date?: string
  event_title?: string
  time_start?: string
  time_end?: string
  selected_lenses?: string[]
  active_question?: string
}

export interface StreamEvent {
  contract_version: 'v8_copilot_api_contract_v0'
  request_id: string
  sequence: number
  event: EventName
  payload: Record<string, unknown>
}

export interface Backing {
  kind: string
  ref: string
}

export interface Claim {
  claim_id?: string
  text: string
  claim_type: string
  backing: Backing
}

export interface AnswerCard {
  question: string
  object_ref: string
  view: string
  as_of: string
  sample_scope: string
  evidence_grade: string
  lens_invocations: Array<Record<string, unknown>>
  lens_gap: Array<Record<string, unknown>>
  source_freshness: Record<string, string>
  body_rows: Array<Record<string, unknown>>
  analysis_claims: Claim[]
  data_debt: Array<Record<string, unknown>>
  data_debt_refs: string[]
  caveats: string[]
  provenance: string[]
}

export interface ResearchResponse {
  request_id: string
  status: 'complete' | 'degraded'
  route: Record<string, unknown>
  interpretation: Record<string, unknown>
  answer_card: AnswerCard | null
  fallback: Record<string, unknown> | null
  claims: Claim[]
  degradations: Array<{ code: string; message: string }>
}

export interface PricePoint {
  date: string
  close: number
}

export interface EventNode {
  event_id: string
  date: string
  title: string
  lane_id: string
  lane_label: string
  episode_label: string
  subtype_label: string
  source_material_label: string
}

export interface StockDossier {
  symbol: string
  display_name: string
  as_of: string
  price_series: PricePoint[]
  status_intervals: Array<Record<string, string | null>>
  event_nodes: EventNode[]
  timeline_lanes: Array<{ lane_id: string; display_label: string; color: string }>
  lens_invocations: Array<Record<string, string>>
  source_freshness: Record<string, string>
  provenance: string[]
}
