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

export type ExperienceStatus = 'candidate'|'accepted'|'ignored'|'merged'|'blocked'|'closed'|'superseded'
export type ExperienceType = 'routing_rule'|'query_plan'|'definition'|'coverage_boundary'|'reasoning_rule'|'presentation_rule'|'anti_pattern'|'materialization_recipe'|'regression_case'

export interface Experience {
  contract_version:string
  experience_id:string
  experience_version:number
  status:ExperienceStatus
  experience_type:ExperienceType
  title:string
  value_summary:string
  trigger_conditions:string[]
  topic_tags:string[]
  scope:string[]
  required_inputs:string[]
  query_plan:string[]
  definitions:string[]
  answer_rubric:string[]
  anti_patterns:string[]
  coverage_boundaries:string[]
  validation_refs:string[]
  source_run_refs:string[]
  supersedes:string[]
  created_at:string
  reviewed_at?:string|null
  reviewed_by?:string|null
  not_evidence:true
}

export interface ExperienceGovernanceStatus {
  accepted_count:number
  candidate_count:number
  blocked_count:number
  conflicts:Array<{conflict_id:string;kind:string;severity:'blocking'|'review';detail:string}>
  latest_regression:Record<string,unknown>|null
  ordinary_success_auto_capture:false
  auto_accept_enabled?:boolean
  auto_accept_min_distinct_runs?:number
  auto_accept_policy?:string
  not_evidence:true
}

export interface ExperienceAutoAcceptance {
  experience_id:string
  outcome:'accepted'|'waiting_for_replication'|'blocked'|'unchanged'
  policy_id:string
  distinct_source_runs:number
  minimum_source_runs:number
  reason:string
  checks:Array<{validation_ref:string;status:'passed'|'failed'|'unverified';detail:string}>
}

export interface ResearchRun {
  run_id:string
  request_id:string
  question_text:string
  normalized_intent:string
  object_refs:string[]
  evidence_pack_ids:string[]
  final_answer:string
  research_draft:Record<string,unknown>
  decision_audit:DecisionAudit|Record<string,never>
  validation_report:{valid?:boolean;issues?:Array<Record<string,unknown>>}
  source_freshness:Record<string,string>
  tool_calls:string[]
  experience_hits:string[]
  experience_candidate_ids:string[]
  feedback_count:number
  agent_surface:string
  model:string
  config_digest:string
  thread_id:string
  turn_id:string
  started_at:string
  completed_at:string
  created_at:string
}

export interface EvidenceBacking {
  kind:string
  ref:string
}

export interface DecisionFactor {
  factor_id:string
  label:string
  direction:'supports'|'weakens'|'limits'|'context'
  importance:'decisive'|'high'|'medium'|'low'
  rationale:string
  backing:EvidenceBacking[]
}

export interface DecisionAlternative {
  label:string
  disposition:'selected'|'rejected'|'unresolved'
  reason:string
  backing:EvidenceBacking[]
}

export interface DecisionAudit {
  weighting_method:'ordinal_evidence_weighting_v0'
  judgment:string
  judgment_backing:EvidenceBacking[]
  confidence:'high'|'medium'|'low'|'insufficient'
  factors:DecisionFactor[]
  alternatives:DecisionAlternative[]
  not_hidden_chain_of_thought:true
}

export interface EvidencePackPayload {
  contract_version:string
  pack_id:string
  pack_digest:string
  question_scope:Record<string,unknown>
  query_plan_id:string
  rows:Array<Record<string,unknown>>
  lens_invocations:Array<Record<string,unknown>>
  external_evidence:Array<Record<string,unknown>>
  freshness_manifest:Record<string,unknown>
  source_freshness:Record<string,string>
  provenance:string[]
  coverage_gaps:Array<Record<string,unknown>>
  definitions:string[]
  allowed_claims:Array<Record<string,unknown>>
  forbidden_inferences:string[]
  validation_catalog:Record<string,string>
  applicable_experiences:Array<Record<string,unknown>>
  deterministic_response:Record<string,unknown>
  not_evidence:false
}

export interface EvidencePackAuditRecord {
  pack_id:string
  pack_digest:string
  payload:EvidencePackPayload
  created_at:string
}

export type ExperienceReviewDecisionValue = 'accept_suggested'|'need_more_evidence'|'reject'|'defer'
export interface ExperienceReviewOption {value:ExperienceReviewDecisionValue;label:string;description:string}
export interface ExperienceReviewExample {run_id:string;question:string;intent:string;answer_excerpt:string;source_pointer:string}
export interface ExperienceReviewCard {
  card_id:string
  experience_id:string
  experience_version:number
  title:string
  affected_area:string
  target_field:'experience_status'
  scope:'experience_cluster'
  decision_requested:string
  why_surfaced:string
  recommendation:ExperienceReviewDecisionValue
  recommendation_label:string
  recommendation_reason:string
  impact:string
  affected_count:number
  options:ExperienceReviewOption[]
  evidence_examples:ExperienceReviewExample[]
  counterexamples:ExperienceReviewExample[]
  prior_decisions:string[]
  experience:Experience
}
export interface ExperienceReviewQueue {
  review_session_id:string
  review_version:'v8_experience_batch_review_v1'
  title:string
  source_packet:string
  created_at:string
  max_pending:number
  cards:ExperienceReviewCard[]
}
export interface ExperienceReviewDecision {
  card_id:string
  decision:ExperienceReviewDecisionValue
  note:string
  target_field:'experience_status'
  affected_area:string
  scope:'experience_cluster'
  recommended_decision:ExperienceReviewDecisionValue
  question:string
}
export interface ExperienceReviewDecisionExport {
  review_session_id:string
  review_version:'v8_experience_batch_review_v1'
  exported_at:string
  source_packet:string
  decisions:ExperienceReviewDecision[]
}

export interface DailyIntelligence {
  contract_version:string
  as_of:string
  checked_through:Record<string,string>
  release_status:Record<string,'descriptive'|'shadow'|'unavailable'>
  coverage:{membership_count:number;activity_row_count:number;turnover_rate_f_coverage:number;full_universe_ready:boolean}
  hard_transitions:Array<Record<string,unknown>>
  priority_announcements:Array<Record<string,unknown>>
  activity_anomalies:Array<Record<string,unknown>>
  research_queue:Array<Record<string,unknown>>
  continuing_watch:Array<Record<string,unknown>>
  overflow_count:number
  risk_notice:string
}
