import type {HistoryEvent,HistoryEventTimeline} from './researchHistoryTypes'

export function eventMarkers(timeline:HistoryEventTimeline|undefined,selected:HistoryEvent|undefined){
  if(!timeline)return []
  const dates=new Set(timeline.events.filter(e=>e.highlight||e.id===selected?.id).map(e=>e.published_on))
  return [...dates].sort().map(date=>{
    const group=timeline.events.filter(e=>e.published_on===date)
    return {date,id:group.find(e=>e.id===selected?.id)?.id||group[0].id,
      label:`公告 ${date}：${group[0].title}${group.length>1?`等${group.length}条`:''}`,
      selected:date===selected?.published_on,count:group.length}
  })
}
