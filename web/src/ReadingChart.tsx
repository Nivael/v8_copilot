import {useEffect,useId,useState} from 'react'
import type {ReadingSeries} from './readingTypes'
import {percent} from './readingFormat'

export function ReadingChart({series,label}:{series:ReadingSeries[];label:string}){
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
  const levels=aligned.flatMap(item=>item.points.map(point=>point.level-100))
  const low=Math.floor(Math.min(0,...levels)/5)*5-2,high=Math.ceil(Math.max(0,...levels)/5)*5+2
  const width=compact?400:940,left=compact?43:54,right=width-(compact?14:20),bottom=compact?226:260
  const x=(index:number)=>left+index/(dates.length-1)*(right-left)
  const y=(level:number)=>26+(high-(level-100))/(high-low)*(bottom-26)
  const selected=Math.min(cursor??dates.length-1,dates.length-1)
  const rough=(high-low)/5,magnitude=10**Math.floor(Math.log10(rough))
  const step=[1,2,5,10].find(value=>value*magnitude>=rough)!*magnitude
  const firstTick=Math.ceil(low/step)*step
  const ticks=Array.from({length:Math.floor((high-firstTick)/step)+1},(_,i)=>firstTick+i*step)
  return <figure className="reading-chart" aria-label={label}>
    <div className="reading-chart-legend">{aligned.map((item,index)=><span key={item.key} className={`reading-series reading-series-${index}`}><i/>{item.name}<strong>{percent(item.change_pct)}</strong></span>)}</div>
    <svg viewBox={`0 0 ${width} ${bottom+36}`} role="img" aria-labelledby={`${id}-title ${id}-desc`} onPointerMove={event=>{
      const rect=event.currentTarget.getBoundingClientRect()
      setCursor(Math.max(0,Math.min(dates.length-1,Math.round(((event.clientX-rect.left)/rect.width*width-left)/(right-left)*(dates.length-1)))))
    }} onPointerLeave={()=>setCursor(null)}>
      <title id={`${id}-title`}>{label}</title><desc id={`${id}-desc`}>同一时期从零涨跌幅起算。可用下方日期滑块逐日查看。</desc>
      {ticks.map(tick=><g key={tick}><line x1={left} x2={right} y1={y(tick+100)} y2={y(tick+100)} className="reading-grid"/><text x={left-10} y={y(tick+100)+4} textAnchor="end">{tick.toFixed(step<1?1:0)}%</text></g>)}
      <line x1={left} x2={right} y1={y(100)} y2={y(100)} className="reading-zero"/>
      {aligned.map((item,index)=><path key={item.key} className={`reading-line reading-line-${index}`} d={item.points.map((point,i)=>`${i?'L':'M'}${x(i).toFixed(2)},${y(point.level).toFixed(2)}`).join(' ')}/>)}
      <line x1={x(selected)} x2={x(selected)} y1="26" y2={bottom} className="reading-cursor"/>
      {aligned.map((item,index)=><circle key={item.key} cx={x(selected)} cy={y(item.points[selected].level)} r="4" className={`reading-dot-${index}`}/>)}
      <text x={left} y={bottom+26}>{dates[0]}</text><text x={right} y={bottom+26} textAnchor="end">{dates.at(-1)}</text>
    </svg>
    <div className="reading-chart-cursor"><time>{dates[selected]}</time>{aligned.map(item=><span key={item.key}>{item.name} <b>{percent(item.points[selected].level-100)}</b></span>)}</div>
    <input type="range" min={0} max={dates.length-1} value={selected} onChange={event=>setCursor(Number(event.target.value))} aria-label={`${label}，选择交易日`} aria-valuetext={dates[selected]}/>
    <details className="reading-chart-data"><summary>逐日数值</summary><div className="reading-scroll"><table><thead><tr><th>日期</th>{aligned.map(item=><th key={item.key}>{item.name}</th>)}</tr></thead><tbody>{dates.map((date,index)=><tr key={date}><th>{date}</th>{aligned.map(item=><td key={item.key}>{percent(item.points[index].level-100)}</td>)}</tr>)}</tbody></table></div></details>
  </figure>
}
