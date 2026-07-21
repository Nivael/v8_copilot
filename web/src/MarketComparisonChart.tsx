import {useEffect, useMemo, useRef} from 'react'
import {ColorType, LineSeries, createChart, type Time} from 'lightweight-charts'
import {comparisonData,type ComparisonRow as Row} from './marketComparisonData'

const SERIES = [
  {key:'stock', label:'个股', color:'#111827'},
  {key:'st', label:'ST等权', color:'#c2413b'},
  {key:'csi2000', label:'中证2000', color:'#b45309'},
  {key:'market', label:'中证全指', color:'#2563a8'},
] as const

export function MarketComparisonChart({rows}:{rows:Row[]}) {
  const containerRef=useRef<HTMLDivElement>(null)
  const {summary,points}=useMemo(()=>comparisonData(rows),[rows])

  useEffect(()=>{
    if(!containerRef.current || !summary || points.length<2)return
    const chart=createChart(containerRef.current,{
      autoSize:true,height:300,
      layout:{background:{type:ColorType.Solid,color:'#ffffff'},textColor:'#68707d'},
      grid:{vertLines:{color:'#f2f3f5'},horzLines:{color:'#eceef1'}},
      rightPriceScale:{borderColor:'#dfe3e8'},
      timeScale:{borderColor:'#dfe3e8',rightOffset:2,barSpacing:18,minBarSpacing:5},
    })
    SERIES.forEach(item=>{
      if(item.key==='stock' && points.every(point=>point.stock===null))return
      const series=chart.addSeries(LineSeries,{
        color:item.color,lineWidth:item.key==='stock'?3:2,
        priceLineVisible:false,lastValueVisible:true,
      })
      series.setData(points.flatMap(point=>{
        const value=point[item.key]
        return value===null?[]:[{time:point.date as Time,value}]
      }))
    })
    chart.timeScale().fitContent()
    return()=>chart.remove()
  },[points,summary])

  if(!summary || points.length<2)return null
  const hasStock=points.some(point=>point.stock!==null)
  const metrics: Array<[string, unknown]>=[
    ['ST等权',summary['ST等权收益']],
    ['中证2000',summary['中证2000收益']],
    ['中证全指',summary['中证全指收益']],
  ]
  if(hasStock)metrics.unshift(['个股',summary['个股收益']])
  const relativeMetrics: Array<[string, unknown]> = [
    ['ST − 中证2000',summary['ST相对中证2000']],
    ['ST − 全市场',summary['ST相对全市场']],
    ['中证2000 − 全市场',summary['中证2000相对全市场']],
  ]
  if(hasStock)relativeMetrics.unshift(
    ['个股 − ST',summary['个股相对ST']],
    ['个股 − 中证2000',summary['个股相对中证2000']],
    ['个股 − 全市场',summary['个股相对全市场']],
  )
  return (
    <section className="market-comparison" aria-label="同窗市场对比">
      <header>
        <div><p className="eyebrow">MARKET CONTEXT</p><h2>同窗市场对比</h2></div>
        <span>{String(summary['窗口起点'])} — {String(summary['窗口终点'])}</span>
      </header>
      <div className="market-metrics">
        {metrics.map(([label,value])=><div key={String(label)}><span>{label}</span><strong>{String(value)}</strong></div>)}
      </div>
      <div className="market-relative" aria-label="相对收益百分点差">
        {relativeMetrics.map(([label,value])=><div key={label}><span>{label}</span><strong>{String(value)}</strong></div>)}
      </div>
      <div className="market-legend">
        {SERIES.filter(item=>hasStock||item.key!=='stock').map(item=><span key={item.key}><i style={{background:item.color}}/>{item.label}</span>)}
      </div>
      <div className="market-chart" ref={containerRef}/>
      <p>起点归一为 100；相对差是收益百分点差，不代表资金净流入。</p>
    </section>
  )
}
