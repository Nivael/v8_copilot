import {useState} from 'react'
import {ReadingChart} from './ReadingChart'
import {HistoryEventTimeline} from './HistoryEventTimeline'
import {eventMarkers} from './historyEventMarkers'
import type {HistoryEventTimeline as Timeline} from './researchHistoryTypes'
import type {ReadingPoint,ReadingSeries} from './readingTypes'

type Member={symbol:string;name:string;conclusion:string;points:ReadingPoint[];timeline:Extract<Timeline,{version:'history_event_timeline_v2'}>;source_refs:{key:string;title:string;url:string}[];gap_notes:{date:string;reason:string;url:string}[]}
export type AnswerCohort={version:'history_answer_cohort_v1';question_id:string;source_run_id:string;asked_on:string;reference_date:string;through:string;summary:string;price_note:string;market:ReadingPoint[];st:ReadingPoint[];st_name:string;members:Member[]}

function CohortMember({cohort,member}:{cohort:AnswerCohort;member:Member}){
  const [selected,setSelected]=useState(member.timeline.initial_event_id)
  const event=member.timeline.events.find(e=>e.id===selected)??member.timeline.events[0]
  const lines:[string,string,ReadingPoint[]][]=[['stock',member.name,member.points],['market','中证全指',cohort.market],['st',cohort.st_name,cohort.st]]
  const series:ReadingSeries[]=lines.map(([key,name,points])=>({key,name,points,change_pct:points.at(-1)?.level==null?null:points.at(-1)!.level!-100}))
  return <section aria-label={`${member.name}旧答名单跟踪`}>
    <h4>{member.name}<small className="history-cohort-code">{member.symbol}</small></h4>
    <p><strong>{member.conclusion}</strong></p>
    <p className="reading-caption">从{cohort.reference_date}收盘观察至{cohort.through}。原问盘中提出，起点包含提问前的当日变动；数字是价格对照。</p>
    <p className="reading-caption">圆点是原提问；菱形可切换公告，查看判断如何更新。</p>
    <ReadingChart label={`${member.name}旧答名单同期走势`} series={series} markers={[{date:cohort.asked_on,id:cohort.question_id,label:`原提问 ${cohort.asked_on} · 回到重点公告`}]} onMarker={()=>setSelected(member.timeline.initial_event_id)} eventMarkers={eventMarkers(member.timeline,event)} onEventMarker={setSelected}/>
    {event&&<HistoryEventTimeline timeline={member.timeline} event={event} onSelect={setSelected} stName={cohort.st_name}/>}
    <details className="reading-disclosure"><summary>这一组价格的口径与来源</summary><p>{cohort.price_note}</p>
      {member.gap_notes.map(note=><p key={note.date}>{note.date}：{note.reason} <a href={note.url} target="_blank" rel="noreferrer">停复牌依据 ↗</a></p>)}
      {member.source_refs.map(source=><p key={source.key}><a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a></p>)}
    </details>
  </section>
}

function CohortBody({cohort}:{cohort:AnswerCohort}){
  const [symbol,setSymbol]=useState(cohort.members[0].symbol)
  const member=cohort.members.find(m=>m.symbol===symbol)??cohort.members[0]
  return <><p>{cohort.summary}</p><label>选择旧答提名的公司<select aria-label="旧答名单公司" value={member.symbol} onChange={e=>setSymbol(e.target.value)}>{cohort.members.map(m=><option key={m.symbol} value={m.symbol}>{m.name}</option>)}</select></label>
    <CohortMember key={member.symbol} cohort={cohort} member={member}/>
  </>
}

export function HistoryAnswerCohort({cohort,questionId,sourceRunId}:{cohort?:AnswerCohort;questionId:string;sourceRunId?:string}){
  const [open,setOpen]=useState(false)
  if(!cohort)return null
  const valid=cohort.version==='history_answer_cohort_v1'&&cohort.question_id===questionId&&!!sourceRunId&&cohort.source_run_id===sourceRunId&&Array.isArray(cohort.members)&&cohort.members.length>0&&new Set(cohort.members.map(m=>m.symbol)).size===cohort.members.length&&cohort.members.every(m=>m.timeline.question_id===questionId&&m.timeline.symbol===m.symbol&&m.timeline.events.length>0&&m.timeline.events.some(e=>e.id===m.timeline.initial_event_id))
  if(!valid)return <p className="reading-caption">旧答名单与本条研究的对应关系需要重新核对，暂不显示其走势。</p>
  return <details className="reading-disclosure history-answer-cohort" onToggle={e=>setOpen(e.currentTarget.open)}>
    <summary>旧答名单：逐只查看公告与走势（{cohort.members.length}只）</summary>
    {open&&<CohortBody key={`${questionId}:${sourceRunId}`} cohort={cohort}/>}
  </details>
}
