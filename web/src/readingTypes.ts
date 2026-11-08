export type ReadingPoint={date:string;value:number|null;level:number|null}
export type ReadingSeries={key:string;name:string;points:ReadingPoint[];change_pct:number|null}
export type CapitalAction={name:string;date:string;judgment:string;detail:string;scope:string;sources:{label:string;url:string}[]}
export type BroadFundEvidence={unit_nav:{availability:string;as_of?:string;fetched_at?:string;observed_funds?:number;sample_funds?:number;sessions?:number;headline?:string;interpretation?:string;basis_note?:string;rows?:{code:string;name:string;as_of:string;unit_nav:string;five_day_share_change_pct:number;five_day_nav_change_pct:number;twenty_day_nav_change_pct:number;five_day_nav_anchor:string;twenty_day_nav_anchor:string;source_url:string;source_label:string}[]};holders:{availability:string;period_start?:string;period_end?:string;headline?:string;interpretation?:string;scope_note?:string;rows?:{code:string;name:string;kind:'feeder_fund'|'no_20pct_holder_reported';period_start:string;period_end:string;published_on:string;holder_label?:string;opening_shares?:string;closing_shares?:string;holding_change_shares?:string;closing_share_pct?:string;sources:{label:string;url:string}[]}[]}}
export type BroadETFReading={fund_evidence?:BroadFundEvidence;availability:'available';as_of:string;start:string;headline:string;interpretation:string;institution_reading:string;sample_funds:number;source_url:string;capital_actions?:{headline:string;summary:string;actions:CapitalAction[]}|null;groups:{name:string;sample_count:number;increasing_5d:number;decreasing_5d:number;five_day_price_change_pct:number;twenty_day_price_change_pct:number;reading:string;source_url:string;funds:{code:string;name:string;five_day_share_change_pct:number;twenty_day_share_change_pct:number;period_share_change_pct:number}[]}[]}
export type MarketReading={
  availability:string;as_of:string;start:string;headline:string;stance:string;summary:string
  latest_price?:{availability:'available';as_of:string;headline:string;stance:string;summary:string;metrics:{day_change_pct:number;five_day_change_pct:number;twenty_day_change_pct:number};reason:{title:string;text:string;source_label:string;source_url:string}}
  metrics:{day_change_pct:number|null;five_day_change_pct:number|null;twenty_day_change_pct:number|null;period_change_pct:number|null;st_change_pct:number|null;advancing_pct:number|null}
  chart:ReadingSeries[];why:{title:string;text:string;source_label:string;source_url:string}[]
  source_notes?:{title:string;text:string;source_label:string;source_url:string}[]
  watch_next:string[];reading_note:string
  broad_etf?:BroadETFReading|{availability:'unavailable'}
  etf:{headline:string;interpretation:string;how_to_read:string;cash_estimate_yuan:number|null;funds:{code:string;name:string;group:string;share_change_pct:number}[]}
}
export type MethodReading={id:string;title:string;summary:string;category:string;status:string;when_to_use:string[];source_run_refs:string[]}
export type CaseReview={assessment:string;takeaways:string[];reviewed_at:string;sources?:{label:string;url:string}[]}
export type CaseReading={
  price_window_note?:{text:string;source_snapshot:string}
  symbol:string;name?:string;as_of?:string;availability:string;last_close?:number|null;headline?:string
  day_change_pct?:number|null;period_change_pct?:number|null;relative_to_st_pp?:number|null;since_research_change_pct?:number|null
  period_path?:ReadingPoint[];last_research_anchor?:{date:string;close:number|null}|null
  source_url?:string;source_label?:string;research_count:number;used_method_ids?:string[]
  latest_quote?:{as_of:string;close:number;day_change_pct:number;five_day_change_pct:number|null;twenty_day_change_pct:number|null;stage:string};current_observation?:SwingNote|null
  history:{run_id:string;completed_at:string;judgment:string;full_answer:string;experience_hits:string[]}[]
  review:CaseReview|null;previous_review?:CaseReview
}
export type LearningReading={availability:string;methods:MethodReading[];categories:string[];cases:CaseReading[];market_context:MarketReading;codex_sync_note:string;inventory:{accepted:number;candidate:number}}
export type ReadingPacket<T>={availability:string;data?:T;as_of?:string;checked_at?:string;refresh:{in_progress:boolean;last_error:string|null}}
export type SwingNote={judgment:string;reasons:string[];watch_next:string[];sources:{label:string;url:string}[]}
export type SwingRow={symbol:string;name:string;as_of:string;close:number;availability:string;day_change_pct:number;five_day_change_pct:number|null;twenty_day_change_pct:number|null;from_window_high_pct:number;from_twenty_day_low_pct:number;five_day_mean_close:number|null;twenty_day_low_close:number;stage:string;latest_amount_yuan:number;path:{date:string;close:number|null;level:number|null}[];note?:SwingNote}
export type SwingReading={availability:string;as_of:string;start:string;horizon:string;groups:{key:string;name:string;pool_count:number;observed_count:number;oversold_count:number;early_repair_count:number;rows:SwingRow[];excluded:{name:string;availability:string}[]}[];analysis?:{headline:string;summary:string;preferred_symbol?:string;focus_by_group?:Record<string,string>;previous_review?:{basis_date:string;summary:string;cases:{symbol:string;name:string;then_judgment:string;day_change_pct:number|null;now_judgment:string}[]}};rules:Record<string,number>;reading_note:string;watchlist:SwingRow[]}
