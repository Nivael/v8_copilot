import {expect,it} from 'vitest'
import source from './fixtures/longStudyLabelRuns.json'
import {readingLabels} from './researchReadingLabels'
import type {ResearchRun} from './types'
it('corrects only bound labels and preserves original records, values and backings',()=>{
 for(const fixture of source){
  const original=structuredClone(fixture) as unknown as ResearchRun
  const before=structuredClone(original);const result=readingLabels(original)
  expect(result.entry).not.toBeNull();expect(result.mismatch).toBe(false);expect(original).toEqual(before)
  expect(result.run.final_answer).toBe(original.final_answer.replace(result.entry!.old_title,result.entry!.new_title))
  expect(result.run.validation_report).toEqual(original.validation_report)
  expect(result.run.evidence_pack_ids).toEqual(original.evidence_pack_ids)
  if('factors'in original.decision_audit&&'factors'in result.run.decision_audit){
   expect(result.run.decision_audit.factors.map(f=>f.rationale)).toEqual(original.decision_audit.factors.map(f=>f.rationale))
   expect(result.run.decision_audit.factors.map(f=>f.backing)).toEqual(original.decision_audit.factors.map(f=>f.backing))
  }
 }
})
it('rejects changed source binding or wording and leaves unrelated runs unchanged',()=>{
 for(const field of ['digest','pack','text']){
  const run=structuredClone(source[2]) as unknown as ResearchRun
  if(field==='digest')(run.validation_report as Record<string,unknown>).draft_digest='changed'
  if(field==='pack')run.evidence_pack_ids=['changed']
  if(field==='text')run.final_answer+='逐项核日线并补单家公司右边界'
  const result=readingLabels(run);expect(result.mismatch).toBe(true);expect(result.run).toBe(run)
 }
 const run={...source[2],run_id:'other'} as unknown as ResearchRun
 expect(readingLabels(run)).toEqual({run,entry:null,mismatch:false})
})
