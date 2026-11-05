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

export type RegressionState = 'current'|'due'|'never_checked'|'needs_recheck'|'unverified'|'failed'|'unknown'
export interface LearningMethod {
  experience_id:string
  title:string
  status:ExperienceStatus
  experience_version:number
  source_ref_count:number
  existing_source_runs:number|null
  validator_passed_source_runs:number|null
  unresolved_source_refs:string[]|null
  unsupported_validation_refs:string[]
  blocking_conflict:boolean
  regression_state:RegressionState
  last_checked_at:string|null
  next_due_at:string|null
  reviewed_at:string|null
  reviewed_by:string|null
  verification_binding?:{last_run_id:string;method_digest:string;software_digest:string}|null
  verification_source?:'readonly_audit'|'governance_ledger'
  verification_notes?:string[]
}
export interface LearningStatus {
  contract_version:'v8_learning_status_v1'
  generated_at:string
  observation_date:string
  timezone:string
  availability:Record<string,'available'|'missing'|'invalid'>
  gaps:string[]
  counts:Record<ExperienceStatus,number>|null
  runs:{total:number;validator_passed:number;with_experience_hits:number;latest_at:string|null}|null
  regression_counts:Record<Exclude<RegressionState,'unknown'>,number>|null
  latest_regression:{run_id:string;completed_at:string;accepted_examined:number;passed:number;failed:number;unverified:number}|null
  readonly_audit?:{availability:string;completed_at?:string;accepted_examined?:number;passed?:number;failed?:number;unverified?:number;content_digest?:string;source_unchanged?:boolean}
  market_updates?:Array<{source_id:string;label:string;availability:string;requested_through:string|null;fetched_at:string|null;observed_through_min:string|null;observed_through_max:string|null;observation_count:number|null;series_at_target:number|null;declared_series:number|null;snapshot_digest:string|null;url:string;note:string;date_basis?:string;observation_date?:string;observed_source_groups?:number|null;verified_membership_venues?:number|null;observation_unit?:string;coverage_unit?:string;coverage_basis?:string}>
  conflicts:Array<{conflict_id:string;severity:'blocking'|'review';detail:string}>
  methods:LearningMethod[]
  freshness:{
    availability:'available'|'missing'|'invalid'
    manifest_id?:string
    generated_at?:string
    declared_status?:string
    universe_as_of?:string|null
    research_symbol_count?:number
    sources:Array<{source_id:string;label:string;as_of:string|null;checked_at:string|null;expected_through:string|null;declared_status:string;age_calendar_days:number|null;row_count:number|null;coverage_count:number|null;source_ref:string}>
    blocking_gaps?:string[]
    coverage_gaps?:string[]
  }
  quality_evaluation:{status:'not_measured';accuracy:null;reason:string}
  automation:{promotion:string;minimum_source_runs:number;periodic_verification:string;schedule_status:'not_observed'}
  read_only:true
  not_evidence:true
}

export interface MarketRiskIndex {
  code:string
  name:string
  through:string|null
  historical_only:boolean
  evaluation_through?:string|null
  source?:string
  return_5d_pct:number|null
  return_20d_pct:number|null
  return_60d_pct:number|null
  max_drawdown_60d_pct:number|null
  from_60d_peak_pct:number|null
  amount_5d_to_20d_ratio:number|null
  recent?:{start:string;end:string;sessions:number;return_pct:number|null;max_drawdown_pct:number|null;from_peak_pct:number|null}|null
  path:Array<{date:string;close:number|null}>
}
export interface SSEHistoryArchive {
  version:string;availability:string;start?:string;through?:string;content_digest?:string;materialized_at?:string
  historical_breadth_ready:false;historical_ST_ready:false;historical_PIT?:false;effect_measured:false
  distinct_securities?:number;expected_security_days?:number;price_responses?:number;observed_trading_days?:number
  not_returned_days?:number;explicit_nontrading_days?:number;registry_source_rows?:number;basis_responses?:number;endpoint_compared_trading?:number
  source_fetched_at?:string;first_price_observed_at?:string;basis_fetched_at?:string;note?:string
  new_listings?:Array<{code:string;listed_on:string;ended_on:string|null;observed_name:string;board:string}>
  ended_listings?:Array<{code:string;listed_on:string;ended_on:string|null;observed_name:string;board:string}>
  days?:Array<{date:string;listed_members:number;observed_trading:number;explicit_nontrading:string[];not_returned:string[];unclosed_observations_included:false}>
}
export interface SSEGapReview {
  version:string;availability:string;start?:string;through?:string;content_digest?:string;materialized_at?:string
  historical_breadth_ready:boolean;historical_ST_ready:false;historical_PIT:false;effect_measured:false
  reviewed_episodes?:number;distinct_companies?:number;closed_episodes?:number;original_pdfs?:number
  not_returned_days?:number;confirmed_missing_days?:number;unresolved_missing_days?:number;unreviewed_missing_days?:number
  source_fetched_at?:string;note?:string
  episodes?:Array<{case_id:string;symbol:string;company:string;kind:string;start_on:string;end_exclusive:string|null
    interval_closed:boolean;window_days:string[];confirmed_missing_days:number;unresolved_missing_days:number;endpoint_nontrading_confirmed:boolean|null
    proofs:Array<{source_url:string;pages:number[];role:string;published_on:string;observed_at:string}>}>
  days?:Array<{date:string;confirmed_suspended:string[];unresolved:string[]}>
}
export interface SZSESTReference {
  availability:string;version?:string;content_digest?:string;materialized_at?:string
  start?:string;through?:string;anchor_on?:string;anchor_members?:number;distinct_members?:number;endpoint_members?:number
  reviewed_transitions?:number;member_day_observations?:number;minimum_coverage?:number;coverage_threshold?:number
  return_pct?:number|null;max_drawdown_pct?:number|null;endpoint_list_observed_on?:string
  combined_ST_ready:false;effect_measured:false;historical_PIT?:false;portfolio_wealth?:false
  source_fetched_at?:string;source_materialized_at?:string;note?:string
  points?:Array<{date:string;member_count:number;observed_members:number;coverage_ratio:number;missing_symbols:string[];daily_return_pct:number|null;close:number|null}>
  events?:Array<{symbol:string;effective_on:string;kind:string;old_name:string;new_name:string|null;source_url:string;proof_page:number;observed_at:string}>
}
export interface STReconstruction {
  version:string;availability:string;start?:string;through?:string;content_digest?:string;materialized_at?:string
  combined_ST_ready:false;historical_membership_verified:false;historical_PIT:false;portfolio_wealth:false;effect_measured:false
  source_venues?:string[];verified_daily_membership_venues?:string[];reconstructed_membership_venues?:string[];coverage_threshold?:number
  sse_anchor_members?:number;sse_distinct_members?:number;sse_endpoint_members?:number;szse_distinct_members?:number;szse_endpoint_members?:number
  sse_reviewed_transitions?:number;szse_reviewed_transitions?:number
  endpoint_list_observed_on?:string;sse_price_fetched_at?:string;szse_price_fetched_at?:string;newest_notice_observed_at?:string;note?:string
  points:Array<{date:string}&Record<'all'|'SSE'|'SZSE',{member_count:number;observed_members:number;coverage_ratio:number;missing_symbols:string[];daily_return_pct:number|null;close:number|null}>>
  metrics?:Record<'all'|'SSE'|'SZSE',{return_pct:number|null;max_drawdown_pct:number|null;minimum_coverage:number;member_day_observations:number;observed_member_days:number}>
  memberships?:Array<{date:string;SSE:string[];SZSE:string[]}>
  events?:Array<{symbol:string;old_name:string;new_name:string;kind:string;effective_on:string;source_url:string;proof_page:number;published_on:string;observed_at:string}>
  catalog?:{items:Array<{symbol:string;published_on:string;title:string;catalog_url:string;triage:string}>;review_level:string;observed_at:string;full_body_review:false;daily_membership_certificate:false}
}
export interface SZSERecheckDifference {
  overlap_observations:number
  changed_observations:number
  changes:Array<{date:string;before:string;after:string;difference:string}>
  new_dates:string[]
  missing_previous_dates:string[]
}
export interface SZSERevisionRecheck {
  version:string;availability:string;share_observations:number;share_changes:number|null;nav_observations:number
  start?:string;through?:string;sessions?:number;first_observed_at?:string;last_observed_at?:string;baseline_fetched_at?:string;baseline_digest?:string;transport?:string
  final_revision_verified:false;share_revision_status:'final_revision_unverified';corporate_actions_checked:false;estimated_net_subscription_yuan:null;note:string
  responses?:Array<{code:string;kind:string;page:number;url:string;observed_at:string;response_sha256:string}>
  funds:Array<{code:string;latest_shares_ten_thousand:string;share_observations:number;nav_observations:number;nav_through:string;
    share_comparison:SZSERecheckDifference;nav_comparison:SZSERecheckDifference;
    issuer_nav_comparison:Pick<SZSERecheckDifference,'overlap_observations'|'changed_observations'|'changes'>}>
}
export interface IssuerDistribution {
  record_on:string;cash_paid_on:string;ex_dividend_on:string|null;off_exchange_record_on:string|null;off_exchange_cash_paid_on:string|null;evaluation_reference_on:string|null
  source_amount_text:string;source_unit_shares:number;amount_yuan_per_share:string
}
export interface ETFIssuerHistory {
  version:string;availability:string;declared_etfs:number;history_tables_observed:number;empty_tables_unconfirmed:number;query_failed_etfs:number
  window_start?:string;through?:string;query_cutoff?:string;completed_at?:string;reparsed_at?:string|null;market_target?:string|null;note:string
  corporate_actions_checked:false;estimated_net_subscription_yuan:null
  funds:Array<{code:string;issuer:string;availability:string;source_url:string;observed_at:string;table_records:number|null;latest_listed_distribution:IssuerDistribution|null
    window_record_date_count:number|null;window_cash_paid_date_count:number|null;window_split_count:number|null;split_table_status:string;splits:Array<{effective_on:string;ratio:string}>
    responses:Array<{method:string;url:string;params:Record<string,unknown>|null;observed_at:string}>}>
}
export interface NodeMarketInputAudit {
  observed_at?:string
  version:string;availability:string;outcomes_read:false;effect_measured:false
  plan:{minimum_test_events:number;minimum_test_companies:number;horizon_sessions:number;anchor_start:string;anchor_end:string}
  test_capacity_events?:number;test_capacity_companies?:number;active_run_linked_events?:number;event_table_rows?:number;unbound_table_rows?:number;main_window_nominations?:number;latest_deterministic_events?:number;conservative_date_shifts?:number
  source_kind_counts?:Record<string,number>;deterministic_lineage_counts?:Record<string,number>;issues?:Record<string,number>;notice?:string;p6_run?:{verified_event_count:number}
  date_reviews?:Array<{document_id:string;company:string;symbol:string;signed_on:string;availability:string;source_url:string;signature_page:number;signature_date_text?:string}>
  folds?:Array<{test_year:number;train_events:number;train_companies:number;test_events:number;test_companies:number;train_capacity_pass:boolean}>
  source_dates?:{benchmark_keys_through:string;historical_membership_through:string;node_information_through:string;price_keys_through:Record<string,string>}
}
export interface ExchangeRiskMembership {
  availability:string;observed_on?:string;started_at?:string;completed_at?:string;reparsed_at?:string|null;is_today_observation?:boolean
  historical_membership_ready:false;common_source_as_of?:null;risk_warning_a_shares?:number;delisting_a_shares?:number;excluded_b_shares?:number;note?:string
  groups?:Array<{group:string;venue:string;board:string;kind:string;source_url:string;source_as_of:string|null;source_rows:number;pages_read:number;a_shares:number;b_shares:number}>
  rows?:Array<{ts_code:string;name:string;share_class:string;kind:string;venue:string;group:string}>
}
export interface MarketRiskETF {
  code:string
  group:string
  through:string|null
  corporate_actions_checked:boolean
  source?:string
  nav_through?:string|null
  nav_source?:string
  nav_source_url?:string
  nav_conflict_dates?:string[]
  nav_crosscheck_observations?:number
  share_revision_unverified?:boolean
  evaluation_through?:string|null
  path?:Array<{date:string;shares:number|null}>
  windows:Record<string,{window_sessions?:number|null;window_start?:string|null;window_end?:string|null;share_change_ten_thousand?:number|null;share_change_pct:number|null;share_change_notional_yuan:number|null;estimated_net_subscription_yuan:number|null;status:string}>
}
export interface MarketBreadthSummary {
  observed_trading_stocks?:number
  listed_source_stocks?:number
  nontrading_stocks?:number
  advancing?:number
  declining?:number
  flat?:number
  declining_5pct_or_more?:number
  median_return_pct?:number|null
  mean_return_pct?:number|null
  declining_share_pct?:number|null
  amount_yuan?:number|null
}
export interface CombinedBreadthHistory {
  version:string;availability:string;start?:string;through?:string;content_digest?:string;materialized_at?:string
  complete_market_history:boolean;historical_ST_ready:false;historical_PIT:false;effect_measured:false;matches_market_target?:boolean
  covered_venues:string[];missing_venues:string[];observed_days?:number;expected_days?:number;observation_count?:number;traded_observation_count?:number
  fetched_at?:string;first_suspension_observed_at?:string;sse_price_fetched_at?:string;szse_fetched_at?:string;source_url?:string;note?:string
  points:Array<{date:string;all:MarketBreadthSummary;SSE:MarketBreadthSummary;SZSE:MarketBreadthSummary}>
  sse_suspensions?:{source_rows:number;ordinary_A_records:number;excluded:Record<string,number>;notice_confirmed_days:number;additional_continuous_days:number
    records:Array<{symbol:string;name_as_reported:string;start_on:string;last_suspended_on:string|null;kind:string;open_when_observed:boolean;reason:string;end_reason:string;window_days:string[]}>}
}
export interface ETFQuarterlyReport {
  code:string
  availability:string
  publication_date?:string
  source_url?:string
  pdf_url?:string|null
  table_page?:number
  opening_shares?:string
  subscription_shares?:string
  redemption_shares?:string
  net_subscription_shares?:string
  closing_shares?:string
  split_entry?:string
  reported_split_shares?:string|null
  accounting_residual_shares?:string
  off_exchange_opening_shares?:string|null
  off_exchange_closing_shares?:string|null
  audit_status?:string
  period_start?:string
  period_end?:string
  document_observed_at?:string
  daily_comparison?:{availability:string;date:string;reported_shares:string|null;difference_from_report_total:string|null;difference_after_explicit_off_exchange:string|null;source_url?:string|null;source_rounding_rule:string}
}
export interface ETFNoticeReview {
  version:string;availability:string;reviewed_notices:number;reviewed_funds:number;distinct_original_pdfs?:number;
  catalog_window_start?:string|null;catalog_window_end?:string|null;
  window_selected_documents:number|null;window_documents_outside_this_review:number|null;category_counts:Record<string,number>;
  corporate_actions_checked:false;all_window_documents_reconciled:false;note:string;
  repeat_disclosure_groups:Array<{code:string;issuer:string;quantity:string;amount_yuan:string;document_ids:string[];not_additional_subscription_flow:true}>;
  notices:Array<{document_id:string;code:string;category:string;title:string;published_on:string;observed_at:string;url:string;evidence_pages:number[];
    fund_share_change_verified:false;full_document_semantics_checked:false;reference_description?:string;listing_on?:string;nav_reference_on?:string;reported_weight_text?:string;risk_clause?:string;
    allocations:Array<{issuer:string;asset_unit:string;quantity:string;amount_yuan:string;table_page:number}>;
    service?:{role:string;provider:string;effective_on:string}}>
}
export interface ETFProspectusRules {
  version:string;availability:string;reviewed_versions:number;selected_prospectus_versions:number|null;
  corporate_actions_checked:false;all_window_documents_reconciled:false;note:string;
  versions:Array<{code:string;availability:string;publication_date:string;document_observed_at:string;pdf_url:string;content_asof:string;financial_data_asof:string;cutoff_exception:string|null;
    financial_audit_status:string;source_page_count:number;reviewed_pages:number[];full_document_semantics_checked:false;corporate_actions_checked:false;market_window_correction_applied:false;
    minimum_units:Array<{route:string;label:string;stated_unit_shares:string;table_page:number;quantity_scope:string;effective_at_market_target:string}>;
    consideration_components:string[];cash_is_only_consideration:false;distribution_mode_as_stated:string;max_annual_distributions_as_stated:number;distribution_condition_as_stated:string;actual_distributions_in_market_window:null;current_cash_flow_yuan:null;
    historical_restatement:{classification:string;event_on:string;registered_on:string;stated_ratio:string;rounding_in_this_version:string;pages:number[];not_historical_point_in_time_evidence:true};
    illustration:{classification:string;before_shares:string;stated_ratio:string;after_shares:string;pages:number[];not_a_verified_event:true}|null}>
}
export interface MarketRiskStatus {
  contract_version:'market_risk_status_v1'
  parameter_version:string
  observation_date:string
  generated_at:string
  snapshot_digest:string|null
  requested_through:string|null
  status:'observed_snapshot'|'historical_only'|'unavailable'
  current_risk_assessment:'not_calibrated'
  indices:MarketRiskIndex[]
  etfs:MarketRiskETF[]
  public_etf_snapshot?:{availability:string;through?:string;fetched_at?:string;gap_count?:number}
  szse_etf_snapshot?:{availability:string;through?:string;revision_note?:string;share_revision_status?:string}
  szse_revision_recheck?:SZSERevisionRecheck
  etf_issuer_history?:ETFIssuerHistory
  public_index_snapshot?:{availability:string;through?:string;scope?:string}
  issuer_nav_snapshot?:{availability:string;through?:string;fetched_at?:string}
  public_breadth_snapshot?:{availability:string;through?:string;fetched_at?:string;scope?:string}
  etf_quarterly?:{version:string;availability:string;period_label?:string;period_start?:string;period_end?:string;capture_completed_at?:string;observed_reports:number;declared_etfs:number;corporate_actions_checked:false;note:string;reports:ETFQuarterlyReport[]}
  etf_report_continuity?:{version:string;availability:string;period_start?:string;period_end?:string;following_period_start?:string;following_period_end?:string;
    capture_completed_at?:string;declared_etfs:number;observed_midyear_reports:number;compared_etfs:number;matched_etfs:number;mismatched_etfs:number;corporate_actions_checked:false;note:string;
    reports:Array<{code:string;midyear_report:ETFQuarterlyReport;quarterly_report:ETFQuarterlyReport;
      comparison:{availability:string;total_relation:string;total_difference_shares:string|null;off_exchange_relation:string;off_exchange_difference_shares:string|null}}>}
  etf_notice_review?:ETFNoticeReview
  etf_prospectus_rules?:ETFProspectusRules
  etf_share_events?:{version:string;availability:string;reviewed_events:number;reconciled_documents:number;selected_documents:number|null;pending_documents?:number;all_selected_documents_reconciled:false;corporate_actions_checked:false;note:string;
    events:Array<{event_id:string;code:string;kind:string;resolution:string;event_date:string;record_date?:string;registration_date?:string;ex_right_date?:string|null;planned_ratio:string|null;effective_ratio:string|null;resolution_published_on:string;within_catalog_window:boolean;holder_rounding?:string;plan_holder_rounding?:string[];source_scope?:string;unit_before_shares?:string;unit_after_shares?:string;
      reported_totals?:Array<{scope:string;before_shares:string;after_shares:string;after_minus_simple_ratio_shares:string}>;
      documents:Array<{document_id:string;role:string;published_on:string;observed_at?:string;format?:string;announced_ratio?:string|null;title:string;url:string;pages:number[]}>}>}
  etf_announcements?:{availability:string;through?:string;window_start?:string;window_end?:string;fetched_at?:string;catalog_etfs:number;declared_etfs:number;record_count:number|null;review_required_count:number|null;corporate_actions_checked:false;note:string;
    fulltext?:{availability:string;required:number|null;text_available:number|null;missing_or_unreadable:number|null;completed_at?:string;semantic_review:string};
    catalogs:Array<{code:string;source_url:string;record_count:number;oldest_publication:string;newest_publication:string;review_required_count:number;review_status:string;
      required_documents:Array<{document_id:string;code:string;published_on:string;title:string;url:string;review_reason:string}>}>}
  market_coverage?:{indices_observed_at_target:number;declared_indices:number;breadth_at_target:boolean;st_style_at_target:boolean;historical_breadth_venues_at_target?:number;st_reference_venues_at_target?:number;st_reconstruction_source_venues_at_target?:number}
  recent_window?:{availability:string;requested_start?:string;start?:string;end?:string;sessions?:number;points?:number;reason?:string}
  recent_observations?:{index_coverage:number;declining_indices:number;etf_share_coverage:number;increasing_share_records:number;decreasing_share_records:number;interpretation:string}
  node_market_comparison?:{status:string;reason:string}
  node_market_input_audit?:NodeMarketInputAudit
  exchange_risk_membership?:ExchangeRiskMembership
  szse_st_reference?:SZSESTReference
  st_reconstruction?:STReconstruction
  sse_history_archive?:SSEHistoryArchive
  sse_gap_review?:SSEGapReview
  combined_breadth_history?:CombinedBreadthHistory
  etf_aggregate:Record<string,{evaluation_through?:string|null;observed_etfs:number;nav_observed_etfs?:number;revision_unconfirmed_etfs?:number;declared_etfs:number;estimated_net_subscription_yuan:null;reason:string}>
  breadth:MarketBreadthSummary&{status:string;source?:string;through?:string;scope?:string;return_basis?:string;historical_path_available?:boolean;
    venues?:Array<MarketBreadthSummary&{venue:string;label:string;url:string;source_rows:number;excluded_b_shares:number;excluded_preferred_shares?:number;through:string}>;
    st_name_group?:MarketBreadthSummary&{definition:string}}
  breadth_history?:{availability:string;scope?:string;start?:string;through?:string;fetched_at?:string;observed_days?:number;expected_days?:number;note?:string;source_url?:string;complete_market_history:false;matches_market_target?:boolean;
    last_recorded_attempt?:{status:string;recorded_at:string;start:string;requested_through:string;completed_days:number;expected_days:number}|null;
    points:Array<MarketBreadthSummary&{date:string;source_rows:number;excluded_b_shares:number;excluded_preferred_shares:number;st_name_group:MarketBreadthSummary}>}
  last_attempt:{status:string;requested_through:string;reason?:string;completed_at:string}|null
  parameters:{trend_windows_sessions:number[];etf_windows_sessions:number[];etf_basket:Record<string,string>;risk_weights:null;risk_thresholds:null}
  limitations:string[]
  sources:Array<{title:string;url:string}>
  gaps:string[]
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
