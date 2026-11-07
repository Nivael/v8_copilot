import {useState} from 'react'
import {ReadingChart} from './ReadingChart'
import {eventMarkers} from './historyEventMarkers'
import type {HistoryEvent,HistoryEventTimeline} from './researchHistoryTypes'
import type {ReadingSeries} from './readingTypes'

export function HistoryCasePeriod({timeline,event,onSelect,askedOn}:{timeline:HistoryEventTimeline;event?:HistoryEvent;onSelect:(id:string)=>void;askedOn:string|null}){
  const [open,setOpen]=useState(false)
  if(timeline.version!=='history_event_timeline_v3')return null
  const period=timeline.case_period,paths=period.paths,stock=paths.stocks[timeline.symbol]
  const lines:[string,string,typeof stock.points][]=[['stock',stock.name,stock.points],['market','中证全指',paths.market],['st',paths.st_name,paths.st]]
  const series:ReadingSeries[]=lines.map(([key,name,points])=>({key,name,points,change_pct:points.at(-1)?.level==null?null:points.at(-1)!.level!-100}))
  return <details className="reading-disclosure history-case-period" onToggle={e=>setOpen(e.currentTarget.open)}>
    <summary>{period.title}</summary>
    {open&&<>
      <p>{period.summary}</p>
      <p className="reading-caption">从{paths.calendar[0]}收盘比较当年价格变化，未计现金分红；原问题提出于{askedOn||'后来'}，提问后的走势在下方另看。</p>
      <ReadingChart series={series} label={`${stock.name}当年案例走势`} eventMarkers={eventMarkers(timeline,event)} onEventMarker={onSelect}/>
      <details className="reading-disclosure"><summary>当年价格口径与来源</summary>
        <p>{period.source_note}</p>
        {period.gap_notes.map(note=><p key={note.date}>{note.date}：{note.reason} <a href={note.url} target="_blank" rel="noreferrer">{note.support_kind==='unverified_source_gap'?'缺报来源':'停牌公告'} ↗</a></p>)}
        {period.source_refs.map(source=><p key={source.key}><a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a></p>)}
      </details>
    </>}
  </details>
}
