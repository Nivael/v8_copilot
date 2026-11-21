import packet from './researchReadingLabels.json'
import type {ResearchRun} from './types'
export function readingLabels(run:ResearchRun){
 const entry=packet.entries.find(e=>e.run_id===run.run_id)
 if(!entry)return {run,entry:null,mismatch:false}
 const draft=run.research_draft as {narrative?:{reasoning_steps?:Array<{title?:string}>};decision_audit?:{factors?:Array<{factor_id:string;label:string}>}}
 const audit=run.decision_audit
 const digest=(run.validation_report as {draft_digest?:unknown}).draft_digest
 const factors=Array.isArray(audit.factors)?audit.factors:[]
 const factor=factors.find(f=>f.factor_id===entry.factor_id)
 if(digest!==entry.draft_digest||JSON.stringify(run.evidence_pack_ids)!==JSON.stringify(entry.pack_ids)||draft.narrative?.reasoning_steps?.[0]?.title!==entry.old_title||factor?.label!==entry.old_factor_label||run.final_answer.split(entry.old_title).length!==2)return {run,entry:null,mismatch:true}
 const projected=structuredClone(run)
 const next=projected.research_draft as typeof draft
 next.narrative!.reasoning_steps![0].title=entry.new_title
 for(const f of next.decision_audit?.factors||[])if(f.factor_id===entry.factor_id&&f.label===entry.old_factor_label)f.label=entry.new_factor_label
 if(Array.isArray(projected.decision_audit.factors))for(const f of projected.decision_audit.factors)if(f.factor_id===entry.factor_id)f.label=entry.new_factor_label
 projected.final_answer=projected.final_answer.replace(entry.old_title,entry.new_title)
 return {run:projected,entry,mismatch:false}
}
