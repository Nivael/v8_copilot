import {CheckCircle2, Clock3, FileClock, ShieldAlert} from 'lucide-react'
import {useEffect, useState} from 'react'
import {getResearchRuns} from './api'
import type {ResearchRun} from './types'

export function RunAudit() {
  const [runs,setRuns]=useState<ResearchRun[]>([])
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')

  useEffect(()=>{
    const controller=new AbortController()
    getResearchRuns(controller.signal).then(setRuns).catch(reason=>{
      if(!(reason instanceof DOMException&&reason.name==='AbortError'))setError('无法读取本地运行审计。')
    }).finally(()=>{if(!controller.signal.aborted)setLoading(false)})
    return()=>controller.abort()
  },[])

  return (
    <div className="audit-page">
      <header><p className="eyebrow"><FileClock size={14}/>Secondary audit surface</p><h1>运行审计</h1><p>原始问题、最终回答和 EvidencePack 引用只用于追溯，不属于可复用经验。</p></header>
      {loading&&<p className="experience-empty">正在读取运行记录…</p>}
      {error&&<p className="experience-error" role="alert">{error}</p>}
      {!loading&&!error&&runs.length===0&&<section className="experience-empty"><h2>还没有 Codex 研究运行</h2><p>通过项目 skill 完成并校验的研究会记录在这里。</p></section>}
      <section className="audit-list">
        {runs.map(run=><article key={run.run_id}>
          <header><div><span>{run.agent_surface}</span><h2>{run.question_text}</h2></div>{run.validation_report.valid?<CheckCircle2 className="valid" aria-label="校验通过"/>:<ShieldAlert className="invalid" aria-label="校验未通过"/>}</header>
          <div className="audit-meta"><span><Clock3 size={13}/>{new Date(run.created_at).toLocaleString('zh-CN')}</span><span>{run.normalized_intent}</span><span>{run.evidence_pack_ids.length} 个 EvidencePack</span><span>{run.experience_candidate_ids.length} 个经验候选</span></div>
          <details><summary>查看回答与审计信息</summary><pre>{run.final_answer}</pre><dl>{Object.entries(run.source_freshness).map(([key,value])=><div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl></details>
        </article>)}
      </section>
    </div>
  )
}
