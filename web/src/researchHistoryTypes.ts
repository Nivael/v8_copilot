import type {ReadingPoint} from './readingTypes'
export type HistoryReview={headline:string;assessment:string;then_quote:string;lessons:string[];explanation:{lens:string;text:string;sources?:{label:string;url:string}[]}[];reviewed_at:string}
export type HistoryOutcome={date:string|null;change_pct:number|null}
export type HistoryQuestion={id:string;asked_at:string;asked_on:string;question:string;kind:string;anchor_date:string|null;basis_note:string;categories:string[];answers:{text:string;summary:string;truncated:boolean}[];sources:{kind:string;url?:string;title?:string}[];outcomes:Record<string,Record<string,HistoryOutcome>>;review:HistoryReview|null}
export type HistoryStock={symbol:string;name:string;original_questions:number;saved_research:number;reviewed:number;first_asked_on:string;last_asked_on:string}
export type HistoryInventory={availability:string;as_of:string;stocks:HistoryStock[];coverage:{original_questions:number;saved_research:number;reviewed_questions:number;stocks:number;source_note:string};categories:string[]}
export type HistoryDetail={availability:string;symbol:string;name:string;as_of:string;questions:HistoryQuestion[];chart_sources:Record<string,ReadingPoint[]>;st_name:string;st_note:string;source_urls:Record<string,string>}
