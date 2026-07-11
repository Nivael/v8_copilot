export type EventName = 'accepted'|'interpreted'|'routed'|'answer_card'|'claim_block'|'degraded'|'completed'|'error'
export type NavigationKind = 'stock'|'date'|'announcement'|'episode'|'lens'|'provenance'|'data_debt'

export interface ResearchContext {
  symbol?: string
  date_range?: {start?:string;end?:string}
  selected_event?: {event_id:string;date?:string;title?:string}
  selected_episode?: string
  selected_lenses?: string[]
  active_question?: string
  answer_card_id?: string
  object_scope?: {kind:string;ref:string}
}
export interface NavigationFocus {kind:'provenance'|'data_debt';ref:string}

export interface StreamEvent { request_id:string; sequence:number; event:EventName; payload:Record<string,unknown> }
export interface Claim { text:string; claim_type:string; backing:{kind:string;ref:string} }
export interface NarrativeStatement { text:string; backing:Array<{kind:string;ref:string}> }
export interface NarrativeStep extends NarrativeStatement { title:string }
export interface ResearchNarrative {
  direct_answer:NarrativeStatement
  reasoning_steps:NarrativeStep[]
  uncertainties:NarrativeStatement[]
  watch_items:NarrativeStatement[]
  basis_note:string
}
export interface BoundaryRewrite { message:string;rewritten_question:string;why:string }
export interface AnswerCard {
  question:string
  object_ref:string
  view:string
  as_of:string
  sample_scope:string
  evidence_grade:string
  lens_invocations:Array<Record<string,unknown>>
  lens_gap:Array<Record<string,unknown>>
  source_freshness:Record<string,string>
  body_rows:Array<Record<string,unknown>>
  analysis_claims:Claim[]
  data_debt:Array<Record<string,unknown>>
  data_debt_refs:string[]
  caveats:string[]
  provenance:string[]
}
export interface QuestionCard {
  id:string
  question:string
  object:{kind:string;ref:string}
  needs_data:string[]
  status:'answerable'|'needs_data'|'needs_review'
  view:string
  source:string
  debt_ref?:string|null
}
export interface DataDebtCandidate { debt_ref:string;gap:string;affects:string }
export interface NavigationRef {
  id:string
  kind:NavigationKind
  label:string
  source_kind:string
  source_ref:string
  href:string
  context:Record<string,string|null>
}
export interface Response {
  contract_version:string
  route:Record<string,unknown>
  interpretation:Record<string,unknown>
  answer_card:AnswerCard|null
  claims:Claim[]
  narrative?:ResearchNarrative|null
  boundary_rewrite?:BoundaryRewrite|null
  gaps:Array<Record<string,unknown>>
  sedimentation_candidates:Array<Record<string,unknown>>
  question_cards:QuestionCard[]
  data_debt_candidates:DataDebtCandidate[]
  navigation_refs:NavigationRef[]
  query_template_id?:string|null
  degraded:boolean
  degraded_reasons:string[]
  llm_used:boolean
}
export interface EventNode { event_id:string; date:string; title:string; episode_type:string; episode_label:string; subtype?:string|null; subtype_label:string; timeline_lane:string; timeline_label:string; provenance_refs:string[]; related_lens_ids:string[] }
export interface Dossier { symbol:string; display_name:string; as_of:string; price_series:Array<{date:string;close:number}>; status_intervals:Array<Record<string,string|null>>; events:EventNode[]; timeline_lanes:Array<{lane_id:string;label:string;event_ids:string[]}>; lens_summaries:Array<Record<string,string|string[]>>; data_gaps:Array<Record<string,string|null>>; display_labels:Record<string,string>; provenance:string[] }
