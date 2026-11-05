export type ReadingPoint={date:string;value:number;level:number}
export type ReadingSeries={key:string;name:string;points:ReadingPoint[];change_pct:number|null}
export type MarketReading={
  availability:string;as_of:string;start:string;headline:string;stance:string;summary:string
  metrics:{day_change_pct:number|null;five_day_change_pct:number|null;twenty_day_change_pct:number|null;period_change_pct:number|null;st_change_pct:number|null;advancing_pct:number|null}
  chart:ReadingSeries[];why:{title:string;text:string;source_label:string;source_url:string}[]
  watch_next:string[];reading_note:string
  etf:{headline:string;interpretation:string;how_to_read:string;cash_estimate_yuan:number|null;funds:{code:string;name:string;group:string;share_change_pct:number}[]}
}
export type MethodReading={id:string;title:string;summary:string;category:string;status:string;when_to_use:string[];source_run_refs:string[]}
export type CaseReview={assessment:string;takeaways:string[];reviewed_at:string}
export type CaseReading={
  symbol:string;name?:string;as_of?:string;availability:string;last_close?:number|null;headline?:string
  day_change_pct?:number|null;period_change_pct?:number|null;relative_to_st_pp?:number|null;since_research_change_pct?:number|null
  period_path?:ReadingPoint[];last_research_anchor?:{date:string;close:number|null}|null
  source_url?:string;research_count:number;used_method_ids?:string[]
  history:{run_id:string;completed_at:string;judgment:string;full_answer:string;experience_hits:string[]}[]
  review:CaseReview|null;previous_review?:CaseReview
}
export type LearningReading={availability:string;methods:MethodReading[];categories:string[];cases:CaseReading[];market_context:MarketReading;codex_sync_note:string;inventory:{accepted:number;candidate:number}}
export type ReadingPacket<T>={availability:string;data?:T;as_of?:string;checked_at?:string;refresh:{in_progress:boolean;last_error:string|null}}
