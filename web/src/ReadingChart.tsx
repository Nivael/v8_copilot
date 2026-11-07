import {useEffect,useId,useState} from 'react'
import type {ReadingSeries} from './readingTypes'
import {percent} from './readingFormat'

type DateRange={from:string;through:string}
function rangePositions(dates:string[],range:DateRange){
  const time=(date:string)=>Date.parse(`${date}T00:00:00Z`)
  const validDay=(date:string)=>Number.isFinite(time(date))&&new Date(time(date)).toISOString().slice(0,10)===date
  if(!validDay(range.from)||!validDay(range.through)||range.from>range.through||range.through<dates[0]||range.from>dates.at(-1)!)return null
  const position=(date:string,edge:number)=>{
    const index=dates.findIndex(day=>day>=date)
    if(index<0)return dates.length-1
    if(dates[index]===date)return Math.max(0,Math.min(dates.length-1,index+edge))
    if(index===0)return 0
    return index-1+(time(date)-time(dates[index-1]))/(time(dates[index])-time(dates[index-1]))
  }
  return {from:position(range.from,-.35),through:position(range.through,.35)}
}

type EventMarker={date:string;id:string;label:string;selected:boolean;count:number}
function eventPosition(dates:string[],day:string){
  const target=Date.parse(day+'T00:00:00Z')
  if(!Number.isFinite(target)||new Date(target).toISOString().slice(0,10)!==day||day<dates[0]||day>dates.at(-1)!)return null
  const next=dates.findIndex(d=>d>=day)
  if(dates[next]===day)return next
  const previous=Date.parse(dates[next-1]+'T00:00:00Z'),end=Date.parse(dates[next]+'T00:00:00Z')
  return next-1+(target-previous)/(end-previous)
}

export function ReadingChart({series,label,markers=[],onMarker,reviewThrough,valueMode='change',dateRange,eventMarkers=[],onEventMarker}:{series:ReadingSeries[];label:string;markers?:{date:string;id:string;label:string}[];onMarker?:(id:string)=>void;reviewThrough?:string;valueMode?:'change'|'index';dateRange?:DateRange;eventMarkers?:EventMarker[];onEventMarker?:(id:string)=>void}){
  const id=useId()
  const [cursor,setCursor]=useState<number|null>(null)
  const [compact,setCompact]=useState(()=>typeof window.matchMedia==='function'&&window.matchMedia('(max-width:700px)').matches)
  useEffect(()=>{
    const query=window.matchMedia?.('(max-width:700px)')
    if(!query)return
    const resize=()=>setCompact(query.matches)
    query.addEventListener('change',resize)
    return()=>query.removeEventListener('change',resize)
  },[])
  const base=series.find(item=>item.points.length>1)
  if(!base)return <p className="reading-muted">走势数据正在更新。</p>
  const dates=base.points.map(point=>point.date)
  const aligned=series.filter(item=>item.points.length===dates.length&&item.points.every((point,index)=>point.date===dates[index]))
  const levels=aligned.flatMap(item=>item.points.filter(point=>point.level!=null).map(point=>point.level!-100))
  const low=Math.floor(Math.min(0,...levels)/5)*5-2,high=Math.ceil(Math.max(0,...levels)/5)*5+2
  const width=compact?400:940,left=compact?43:54,right=width-(compact?14:20),bottom=compact?226:260
  const x=(index:number)=>left+index/(dates.length-1)*(right-left)
  const y=(level:number)=>26+(high-(level-100))/(high-low)*(bottom-26)
  const selected=Math.min(cursor??dates.length-1,dates.length-1)
  const rough=(high-low)/5,magnitude=10**Math.floor(Math.log10(rough))
  const step=[1,2,5,10].find(value=>value*magnitude>=rough)!*magnitude
  const firstTick=Math.ceil(low/step)*step
  const ticks=Array.from({length:Math.floor((high-firstTick)/step)+1},(_,i)=>firstTick+i*step)
  const reviewIndex=reviewThrough?dates.indexOf(reviewThrough):-1
  const hasLater=reviewIndex>=0&&reviewIndex<dates.length-1
  const range=dateRange?rangePositions(dates,dateRange):null
  const bandStart=range?Math.max(left,Math.min(right-2,x(range.from))):0
  const bandEnd=range?Math.max(bandStart+2,Math.min(right,x(range.through))):0
  const display=(level:number|null)=>valueMode==='index'?(level==null?'待更新':level.toFixed(2)):percent(level==null?null:level-100)
  const events=eventMarkers.flatMap(marker=>{const position=eventPosition(dates,marker.date);return position==null?[]:[{...marker,position}]})
  const footer=events.length?64:36
  return <figure className="reading-chart" aria-label={label}>
    <div className="reading-chart-legend">{aligned.map((item,index)=><span key={item.key} className={`reading-series reading-series-${index}`}><i/>{item.name}<strong>{valueMode==='index'?display(item.points.at(-1)?.level??null):percent(item.change_pct)}</strong></span>)}</div>
    <svg viewBox={`0 0 ${width} ${bottom+footer}`} role="img" aria-labelledby={`${id}-title ${id}-desc`} onPointerMove={event=>{
      const rect=event.currentTarget.getBoundingClientRect()
      setCursor(Math.max(0,Math.min(dates.length-1,Math.round(((event.clientX-rect.left)/rect.width*width-left)/(right-left)*(dates.length-1)))))
    }} onPointerLeave={()=>setCursor(null)}>
      <title id={`${id}-title`}>{label}</title><desc id={`${id}-desc`}>{valueMode==='index'?'以图中观察起点收盘为100，不以提问日计算收益。':'同一时期从零涨跌幅起算。'}{range&&`阴影表示可能提问区间：${dateRange!.from}至${dateRange!.through}。`}可用下方日期滑块逐日查看。</desc>
      {hasLater&&<rect x={x(reviewIndex)} y="26" width={right-x(reviewIndex)} height={bottom-26} className="reading-after-review"><title>复盘窗口之后的走势</title></rect>}
      {range&&<g className="reading-date-range" role="group" aria-label={`可能提问区间：${dateRange!.from}至${dateRange!.through}`}><rect x={bandStart} y="26" width={bandEnd-bandStart} height={bottom-26}/><line x1={bandStart} x2={bandStart} y1="26" y2={bottom}/><line x1={bandEnd} x2={bandEnd} y1="26" y2={bottom}/></g>}
      {ticks.map(tick=><g key={tick}><line x1={left} x2={right} y1={y(tick+100)} y2={y(tick+100)} className="reading-grid"/><text x={left-10} y={y(tick+100)+4} textAnchor="end">{valueMode==='index'?(tick+100).toFixed(step<1?1:0):`${tick.toFixed(step<1?1:0)}%`}</text></g>)}
      <line x1={left} x2={right} y1={y(100)} y2={y(100)} className="reading-zero"/>
      {aligned.map((item,index)=>{let connected=false;return <path key={item.key} className={`reading-line reading-line-${index}`} d={item.points.map((point,i)=>{if(point.level==null){connected=false;return ''}const command=connected?'L':'M';connected=true;return `${command}${x(i).toFixed(2)},${y(point.level).toFixed(2)}`}).join(' ')}/>})}
      {hasLater&&<g className="reading-review-boundary"><line x1={x(reviewIndex)} x2={x(reviewIndex)} y1="26" y2={bottom}/><text x={Math.max(left,Math.min(x(reviewIndex)+7,right-145))} y="17">复盘截至 {reviewThrough}</text></g>}
      {markers.filter(marker=>dates.includes(marker.date)).map(marker=>{const index=dates.indexOf(marker.date),level=aligned[0]?.points[index]?.level;return <g key={marker.id} role="button" tabIndex={0} aria-label={marker.label} className="reading-question-marker" onClick={()=>onMarker?.(marker.id)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onMarker?.(marker.id)}}}><title>{marker.label}</title><circle cx={x(index)} cy={level==null?bottom:y(level)} r="7"/><circle cx={x(index)} cy={level==null?bottom:y(level)} r="14" fill="transparent" stroke="none"/></g>})}
      <line x1={x(selected)} x2={x(selected)} y1="26" y2={bottom} className="reading-cursor"/>
      {aligned.map((item,index)=>item.points[selected].level==null?null:<circle key={item.key} cx={x(selected)} cy={y(item.points[selected].level!)} r="4" className={`reading-dot-${index}`}/>)}
      {events.map(marker=><g key={marker.id} role="button" tabIndex={0} aria-label={marker.label} aria-pressed={marker.selected} className={`reading-event-marker${marker.selected?' is-selected':''}`} onClick={()=>onEventMarker?.(marker.id)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onEventMarker?.(marker.id)}}}><title>{marker.label}</title>{marker.selected&&<line x1={x(marker.position)} x2={x(marker.position)} y1="26" y2={bottom+18}/>}<path d={`M${x(marker.position)},${bottom+8} l10,10 -10,10 -10,-10 Z`}/>{marker.count>1&&<text x={x(marker.position)} y={bottom+22} textAnchor="middle">{marker.count}</text>}<circle cx={x(marker.position)} cy={bottom+18} r="17" fill="transparent" stroke="none"/></g>)}
      <text x={left} y={bottom+footer-10}>{dates[0]}</text><text x={right} y={bottom+footer-10} textAnchor="end">{dates.at(-1)}</text>
    </svg>
    <div className="reading-chart-cursor"><time>{dates[selected]}</time>{aligned.map(item=><span key={item.key}>{item.name} <b>{display(item.points[selected].level)}</b></span>)}</div>
    <input type="range" min={0} max={dates.length-1} value={selected} onChange={event=>setCursor(Number(event.target.value))} aria-label={`${label}，选择交易日`} aria-valuetext={dates[selected]}/>
    {aligned.some(item=>item.points.some(point=>point.level==null))&&<p className="reading-caption">曲线空档表示缺少可用报价，不按零涨跌补齐。</p>}
    <details className="reading-chart-data"><summary>逐日数值</summary><div className="reading-scroll"><table><thead><tr><th>日期</th>{aligned.map(item=><th key={item.key}>{item.name}</th>)}</tr></thead><tbody>{dates.map((date,index)=><tr key={date}><th>{date}</th>{aligned.map(item=><td key={item.key}>{display(item.points[index].level)}</td>)}</tr>)}</tbody></table></div></details>
  </figure>
}
