import {Check, ClipboardList, Download, LoaderCircle, Save} from 'lucide-react'
import {useEffect,useMemo,useState} from 'react'
import {submitExperienceReviewDecisions} from './api'
import {ExperienceDetailList} from './ExperienceDetailList'
import type {ExperienceReviewDecision,ExperienceReviewDecisionExport,ExperienceReviewDecisionValue,ExperienceReviewQueue} from './types'

interface DraftDecision {decision:ExperienceReviewDecisionValue;note:string}

function storageKey(queue:ExperienceReviewQueue){return `v8-experience-review:${queue.review_session_id}`}

function buildExport(queue:ExperienceReviewQueue,drafts:Record<string,DraftDecision>):ExperienceReviewDecisionExport {
  const decisions:ExperienceReviewDecision[]=queue.cards.flatMap(card=>{
    const draft=drafts[card.card_id]
    if(!draft)return []
    return [{
      card_id:card.card_id,decision:draft.decision,note:draft.note,
      target_field:card.target_field,affected_area:card.affected_area,scope:card.scope,
      recommended_decision:card.recommendation,question:card.decision_requested,
    }]
  })
  return {
    review_session_id:queue.review_session_id,review_version:queue.review_version,
    exported_at:new Date().toISOString(),source_packet:queue.source_packet,decisions,
  }
}

export function ExperienceReviewPanel({queue,onApplied}:{queue:ExperienceReviewQueue;onApplied:()=>void}) {
  const [drafts,setDrafts]=useState<Record<string,DraftDecision>>({})
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [saved,setSaved]=useState(true)

  useEffect(()=>{
    const raw=localStorage.getItem(storageKey(queue))
    if(raw){try{setDrafts(JSON.parse(raw) as Record<string,DraftDecision>)}catch{setDrafts({})}}
    else setDrafts({})
  },[queue])

  useEffect(()=>{
    localStorage.setItem(storageKey(queue),JSON.stringify(drafts))
    setSaved(true)
  },[drafts,queue])

  const payload=useMemo(()=>buildExport(queue,drafts),[queue,drafts])
  const decided=payload.decisions.length
  const pending=queue.cards.length-decided

  function update(cardId:string,decision:ExperienceReviewDecisionValue){
    setSaved(false)
    setDrafts(current=>({...current,[cardId]:{decision,note:current[cardId]?.note||''}}))
  }

  function updateNote(cardId:string,note:string){
    setSaved(false)
    setDrafts(current=>({...current,[cardId]:{decision:current[cardId]?.decision||'defer',note}}))
  }

  function download(){
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}))
    const anchor=document.createElement('a');anchor.href=url;anchor.download=`${queue.review_session_id}.json`;anchor.click();URL.revokeObjectURL(url)
  }

  async function submit(){
    if(!payload.decisions.length)return
    setBusy(true);setError('')
    try{await submitExperienceReviewDecisions(payload);localStorage.removeItem(storageKey(queue));onApplied()}
    catch{setError('批量决定未写入，草稿仍保存在本机浏览器。')}
    finally{setBusy(false)}
  }

  return <section className="review-panel" aria-label="经验批量审阅">
    <header className="review-sticky">
      <div><p><ClipboardList size={15}/>本轮最多 {queue.max_pending} 个方法簇</p><strong>{decided}/{queue.cards.length} 已决定 · {pending} 待处理</strong><span><Save size={13}/>{saved?'草稿已自动保存':'正在保存'}</span></div>
      <div><button type="button" onClick={download} disabled={!decided}><Download size={15}/>导出 JSON</button><button className="accept" type="button" onClick={submit} disabled={!decided||busy}>{busy?<LoaderCircle className="spin" size={15}/>:<Check size={15}/>}提交已选决定</button></div>
    </header>
    {error&&<p className="experience-error" role="alert">{error}</p>}
    <div className="review-layout">
      <div className="review-cards">{queue.cards.map((card,index)=><article className="review-card" key={card.card_id}>
        <header><span>{index+1}/{queue.cards.length}</span><span>{card.affected_area}</span><h2>{card.title}</h2></header>
        <p className="review-question">{card.decision_requested}</p>
        <section className="review-recommendation"><strong>{card.recommendation_label}</strong><p>{card.recommendation_reason}</p></section>
        <div className="review-context"><p><strong>为什么出现：</strong>{card.why_surfaced}</p><p><strong>影响：</strong>{card.impact}</p></div>
        <div className="experience-triggers">{card.experience.topic_tags.map(tag=><span className="topic-tag" key={tag}>{tag}</span>)}</div>
        <fieldset><legend>你的决定</legend>{card.options.map(option=><label key={option.value} className={drafts[card.card_id]?.decision===option.value?'selected':''}><input type="radio" name={`decision-${card.card_id}`} value={option.value} checked={drafts[card.card_id]?.decision===option.value} onChange={()=>update(card.card_id,option.value)}/><span><strong>{option.label}{option.value===card.recommendation?'（推荐）':''}</strong><small>{option.description}</small></span></label>)}</fieldset>
        <label className="review-note">可选备注<textarea value={drafts[card.card_id]?.note||''} onChange={event=>updateNote(card.card_id,event.target.value)} placeholder="不填也可以；系统行为只由上面的结构化选择决定。"/></label>
        <details><summary>查看方法、边界和代表运行</summary><div className="experience-details"><ExperienceDetailList title="查询计划" values={card.experience.query_plan}/><ExperienceDetailList title="输出要求" values={card.experience.answer_rubric}/><ExperienceDetailList title="反模式" values={card.experience.anti_patterns}/><ExperienceDetailList title="覆盖边界" values={card.experience.coverage_boundaries}/></div><div className="review-examples"><h3>代表运行</h3>{card.evidence_examples.length?card.evidence_examples.map(example=><article key={example.run_id}><strong>{example.question}</strong><span>{example.intent} · {example.run_id}</span><p>{example.answer_excerpt}</p></article>):<p>暂无可核对的真实运行，建议选择“需要更多证据”。</p>}</div></details>
      </article>)}</div>
      <aside className="review-preview"><h2>决策 JSON 预览</h2><p>这是将写入独立审阅层的结构化内容。</p><pre>{JSON.stringify(payload,null,2)}</pre></aside>
    </div>
  </section>
}
