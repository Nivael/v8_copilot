import {CheckCircle2, ChevronDown, Clock3, FileClock, Scale, ShieldAlert} from 'lucide-react'
import {useEffect, useMemo, useState} from 'react'
import {getEvidencePack, getResearchRuns} from './api'
import type {
  DecisionAudit, EvidenceBacking, EvidencePackAuditRecord, ResearchRun,
} from './types'

const importanceLabels={decisive:'决定性',high:'高',medium:'中',low:'低'} as const
const directionLabels={supports:'支持',weakens:'削弱',limits:'限制',context:'背景'} as const
const dispositionLabels={selected:'采纳',rejected:'排除',unresolved:'未决'} as const

function isDecisionAudit(value:ResearchRun['decision_audit']):value is DecisionAudit {
  return Array.isArray((value as DecisionAudit).factors)
}

function extractNarrativeBackings(run:ResearchRun) {
  const narrative=(run.research_draft as {narrative?:Record<string,unknown>}).narrative
  if(!narrative)return []
  const candidates:unknown[]=[
    narrative.direct_answer,
    ...((narrative.reasoning_steps as unknown[])||[]),
    ...((narrative.uncertainties as unknown[])||[]),
    ...((narrative.watch_items as unknown[])||[]),
  ]
  return candidates.flatMap(item=>{
    if(!item||typeof item!=='object')return []
    const row=item as {text?:unknown;title?:unknown;backing?:unknown}
    if(typeof row.text!=='string'||!Array.isArray(row.backing))return []
    return [{
      label:typeof row.title==='string'?row.title:row.text,
      text:row.text,
      backing:row.backing as EvidenceBacking[],
    }]
  })
}

function DecisionAuditView({audit}:{audit:DecisionAudit}) {
  return <section className="decision-audit" aria-label="判断权重审计">
    <header><Scale size={16}/><div><h3>判断权重审计</h3><p>{audit.judgment}</p></div><span>置信度：{audit.confidence}</span></header>
    <div className="decision-factors">
      {audit.factors.map(factor=><article key={factor.factor_id}>
        <div><strong>{factor.label}</strong><span className={`importance importance-${factor.importance}`}>{importanceLabels[factor.importance]}</span><span>{directionLabels[factor.direction]}</span></div>
        <p>{factor.rationale}</p>
        <code>{factor.backing.map(ref=>`${ref.kind}:${ref.ref}`).join(' · ')}</code>
      </article>)}
    </div>
    {audit.alternatives.length>0&&<details><summary>查看备选解释如何处理</summary><ul>{audit.alternatives.map((item,index)=><li key={`${item.label}-${index}`}><strong>{dispositionLabels[item.disposition]}：{item.label}</strong><span>{item.reason}</span></li>)}</ul></details>}
    <p className="audit-boundary">这是回答者提交并经 backing 校验的结构化判断说明，不是模型隐藏思维过程，也不使用伪精确概率。</p>
  </section>
}

function EvidencePackView({packId,run}:{packId:string;run:ResearchRun}) {
  const [open,setOpen]=useState(false)
  const [record,setRecord]=useState<EvidencePackAuditRecord|null>(null)
  const [error,setError]=useState('')
  const [loading,setLoading]=useState(false)
  const backings=useMemo(()=>extractNarrativeBackings(run),[run])

  const toggle=()=>{
    const next=!open
    setOpen(next)
    if(!next||record||loading)return
    setLoading(true)
    getEvidencePack(packId).then(setRecord).catch(()=>setError('该运行没有可展开的完整 EvidencePack；旧记录可能只保存了 ID。')).finally(()=>setLoading(false))
  }

  return <div className="pack-audit">
    <button type="button" onClick={toggle} aria-expanded={open}><ChevronDown size={14}/><code>{packId}</code><span>{open?'收起':'展开证据包'}</span></button>
    {open&&<div className="pack-body">
      {loading&&<p>正在读取 EvidencePack…</p>}
      {error&&<p className="experience-error" role="alert">{error}</p>}
      {record&&<>
        <div className="pack-summary"><span>查询计划：{record.payload.query_plan_id}</span><span>Digest：{record.pack_digest.slice(0,16)}…</span><span>Manifest：{String(record.payload.freshness_manifest.manifest_id||record.payload.freshness_manifest.status||'未记录')}</span><span>{record.payload.rows.length} 行数据库证据</span><span>{record.payload.lens_invocations.length} 条 Lens</span><span>{record.payload.external_evidence?.length||0} 项联网事实</span></div>
        <section><h4>数据库行</h4>{record.payload.rows.length?<div className="audit-json-list">{record.payload.rows.map((row,index)=><details key={String(row.row_id||index)}><summary>{String(row.row_id||`row-${index+1}`)}</summary><pre>{JSON.stringify(row,null,2)}</pre></details>)}</div>:<p>本 EvidencePack 没有数据库行。</p>}</section>
        <section><h4>Lens 调用</h4>{record.payload.lens_invocations.length?<div className="audit-json-list">{record.payload.lens_invocations.map((lens,index)=><details key={String(lens.release_id||index)}><summary>{String(lens.release_id||`lens-${index+1}`)} · {String(lens.contributed_section||'未标注贡献段')}</summary><pre>{JSON.stringify(lens,null,2)}</pre></details>)}</div>:<p>本题未调用适用 Lens；这不等于没有数据库事实证据。</p>}</section>
        <section><h4>联网事实</h4>{record.payload.external_evidence?.length?<div className="audit-json-list">{record.payload.external_evidence.map((item,index)=><details key={String(item.evidence_id||index)}><summary>{String(item.evidence_id||`external-${index+1}`)} · {String(item.title||'未命名来源')}</summary><pre>{JSON.stringify(item,null,2)}</pre></details>)}</div>:<p>本 EvidencePack 没有联网补充事实；所有 backing 均来自本地确定性证据。</p>}</section>
        <section><h4>回答 backing</h4>{backings.length?<ul className="backing-list">{backings.map((item,index)=><li key={`${item.label}-${index}`}><strong>{item.label}</strong><span>{item.text}</span><code>{item.backing.map(ref=>`${ref.kind}:${ref.ref}`).join(' · ')}</code></li>)}</ul>:<p>该运行没有保存结构化研究稿；旧记录只能查看最终文本。</p>}</section>
        <section><h4>Coverage gap</h4>{record.payload.coverage_gaps.length?<div className="audit-json-list">{record.payload.coverage_gaps.map((gap,index)=><pre key={index}>{JSON.stringify(gap,null,2)}</pre>)}</div>:<p>EvidencePack 没有声明 coverage gap。</p>}</section>
        <section><h4>允许与禁止的推断</h4><div className="inference-columns"><div><strong>允许结论</strong><pre>{JSON.stringify(record.payload.allowed_claims,null,2)}</pre></div><div><strong>禁止推断</strong><ul>{record.payload.forbidden_inferences.map(item=><li key={item}>{item}</li>)}</ul></div></div></section>
      </>}
    </div>}
  </div>
}

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
      <header><p className="eyebrow"><FileClock size={14}/>Secondary audit surface</p><h1>运行审计</h1><p>这里追溯回答用了什么事实、Lens 和判断因素；原始问题与回答不会变成下一次回答的事实来源。</p></header>
      {loading&&<p className="experience-empty">正在读取运行记录…</p>}
      {error&&<p className="experience-error" role="alert">{error}</p>}
      {!loading&&!error&&runs.length===0&&<section className="experience-empty"><h2>还没有 Codex 研究运行</h2><p>通过项目 skill 完成并校验的研究会记录在这里。</p></section>}
      <section className="audit-list">
        {runs.map(run=><article key={run.run_id}>
          <header><div><span>{run.agent_surface}</span><h2>{run.question_text}</h2></div>{run.validation_report.valid?<CheckCircle2 className="valid" aria-label="校验通过"/>:<ShieldAlert className="invalid" aria-label="校验未通过"/>}</header>
          <div className="audit-meta"><span><Clock3 size={13}/>{new Date(run.created_at).toLocaleString('zh-CN')}</span><span>{run.normalized_intent}</span><span>{run.evidence_pack_ids.length} 个 EvidencePack</span><span>{run.experience_candidate_ids.length} 个经验候选</span></div>
          <details><summary>查看回答与基础审计</summary><pre>{run.final_answer}</pre><dl>{Object.entries(run.source_freshness).map(([key,value])=><div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl><pre>{JSON.stringify(run.validation_report,null,2)}</pre></details>
          {isDecisionAudit(run.decision_audit)?<DecisionAuditView audit={run.decision_audit}/>:<p className="audit-missing">该旧运行没有结构化判断权重审计。</p>}
          <section className="pack-list" aria-label="EvidencePack 列表"><h3>EvidencePack</h3>{run.evidence_pack_ids.map(packId=><EvidencePackView key={packId} packId={packId} run={run}/>)}</section>
        </article>)}
      </section>
    </div>
  )
}
