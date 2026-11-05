import {useState} from 'react'
import type {MarketRiskIndex,SZSESTReference as Reference} from './types'

const pct=(value:number|null|undefined)=>value==null?'—':`${value>0?'+':''}${value.toFixed(2)}%`
const coverage=(value:number|undefined)=>value==null?'—':`${(value*100).toFixed(2)}%`
const kinds:Record<string,string>={warning_added:'实施风险警示',warning_removed:'撤销风险警示',delisting_period:'进入退市整理期',listing_end:'摘牌'}
const time=(value:string)=>new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})

export function SZSESTReference({data,indices}:{data:Reference;indices:MarketRiskIndex[]}){
  const points=data.points??[]
  const [position,setPosition]=useState<number|null>(null)
  const ready=data.availability==='observed'&&points.length>=2&&points[0].date===data.start&&points.at(-1)?.date===data.through
    &&points.every(p=>p.close!=null&&Number.isFinite(p.close)&&p.close>0&&p.coverage_ratio>=(data.coverage_threshold??1))
  const index=Math.min(position??points.length-1,points.length-1)
  const selected=points[index]
  const market=indices.find(item=>item.code==='000985.CSI'&&!item.historical_only&&item.through===data.through)
  const marketPath=market?.path.filter(p=>data.start!=null&&p.date>=data.start&&data.through!=null&&p.date<=data.through)??[]
  const matched=ready&&marketPath.length===points.length&&marketPath.every((p,i)=>p.date===points[i].date&&p.close!=null&&Number.isFinite(p.close)&&p.close>0)
  const st=ready?points.map(p=>p.close!/points[0].close!*100):[]
  const broad=matched?marketPath.map(p=>p.close!/marketPath[0].close!*100):[]
  const lo=Math.floor(Math.min(100,...st,...broad)/5)*5-2
  const hi=Math.ceil(Math.max(100,...st,...broad)/5)*5+2
  const x=(i:number)=>48+i*760/(points.length-1)
  const y=(value:number)=>216-(value-lo)/(hi-lo)*190
  const path=(values:number[])=>values.map((value,i)=>`${i===0?'M':'L'}${x(i).toFixed(2)},${y(value).toFixed(2)}`).join(' ')
  return <section className="learning-freshness market-st-reference" aria-label="深市ST同期价格参考">
    <header className="learning-section-head"><div><p className="eyebrow">ST风格 / 逐日成员核对</p><h2>深市ST有成交样本价格参考</h2></div><span>{ready?'交易所覆盖 1/2 · 仅深市':'暂无有效价格路径'}</span></header>
    {!ready?<p className="learning-empty">当前没有完整通过来源及每日成交覆盖核对的价格路径；任一日不足时，整段曲线与窗口指标均不发布。</p>:<>
      <p>{data.start} 至 {data.through}，{points.length}个收盘点、{points.length-1}个交易日跨度。起始名单 {data.anchor_members} 只，期间共 {data.distinct_members} 只；{data.reviewed_transitions}处公告生效变化逐日核对，期末 {data.endpoint_members} 只。</p>
      <div className="market-recent-grid"><article><span>窗口价格参考变化</span><strong>{pct(data.return_pct)}</strong><small>首个收盘点归一为100</small></article><article><span>窗口最大回撤</span><strong>{pct(data.max_drawdown_pct)}</strong><small>按这条价格参考路径计算</small></article><article><span>最低每日成交覆盖</span><strong>{coverage(data.minimum_coverage)}</strong><small>固定门槛 {coverage(data.coverage_threshold)}；停牌保留分母</small></article></div>
      <div className="market-risk-legend"><span><i/>深市ST有成交样本</span>{matched&&<span><i className="market-line-1"/>中证全指 · 同窗</span>}</div>
      <svg className="market-st-chart" viewBox="0 0 840 250" role="img" aria-label={matched?'深市ST与同期市场价格参考路径':'深市ST价格参考路径'}>
        <title>深市ST有成交样本价格参考，首个收盘点为100</title>
        {[lo,(lo+hi)/2,hi].map(tick=><g key={tick}><line x1="48" x2="808" y1={y(tick)} y2={y(tick)} stroke="#e2e9df"/><text x="40" y={y(tick)+4} textAnchor="end">{Number.isInteger(tick)?tick.toFixed(0):tick.toFixed(1)}</text></g>)}
        <line x1="48" x2="808" y1={y(100)} y2={y(100)} stroke="#aab8aa" strokeDasharray="4 4"/>
        <path d={path(st)} stroke="#3d684d"/>{matched&&<path d={path(broad)} stroke="#a47845"/>}
        <line x1={x(index)} x2={x(index)} y1="20" y2="216" stroke="#788d7b" strokeDasharray="3 3"/>
        <circle cx={x(index)} cy={y(st[index])} r="4" fill="#3d684d"/>
        {[0,Math.floor((points.length-1)/2),points.length-1].map(i=><text key={i} x={x(i)} y="240" textAnchor={i===0?'start':i===points.length-1?'end':'middle'}>{points[i].date}</text>)}
      </svg>
      {!matched&&<p>中证全指缺少完整一致的日期序列，当前不叠加市场对照线。</p>}
      <label className="market-st-slider">逐日查看 <input type="range" min="0" max={points.length-1} value={index} aria-label="ST参考观察日期" aria-valuetext={selected.date} onChange={event=>setPosition(Number(event.target.value))}/></label>
      <div className="market-st-readout" aria-live="polite"><strong>{selected.date}</strong><span>ST参考 {st[index].toFixed(2)}{matched&&` · 中证全指 ${broad[index].toFixed(2)}`}</span><span>成员 {selected.member_count} · 有成交 {selected.observed_members} · 覆盖 {coverage(selected.coverage_ratio)}</span><span>停牌或缺失：{selected.missing_symbols.join('、')||'无'}</span></div>
      <p className="learning-footnote">每日按当日有成交成员的收盘价/前收参考价计算均值并连接；停牌与缺失不填零。每日成员及有成交样本会变化，这是描述性的价格参考，不是组合财富或全收益。进入退市整理期或摘牌后退出该类别，不将原股东损益记作零。</p>
      <p className="learning-footnote">仅深市，尚非沪深整体ST走势。历史日表与公告均在所示日期之后取得；这段已知压力窗口不能证明市场因素优于节点，也不用于校准风险权重。</p>
      <details className="market-source-notes"><summary>查看成员生效依据与每日覆盖</summary>
        <p>起始成员来自 {data.anchor_on} 的独立历史名单；逐日ST名称组用于核对变化，{data.reviewed_transitions}处变化另有原公告生效依据。期末代码与读取于 {data.endpoint_list_observed_on} 的深市交易所名单一致；该次读取日期不回填为历史名单日期。</p>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的ST成员生效依据表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">证券与名称变化</th><th scope="col">生效日期 / 事项</th><th scope="col">原公告依据</th></tr></thead><tbody>{data.events?.map(event=><tr key={event.symbol+event.effective_on}><th scope="row">{event.symbol}<small>{event.old_name} → {event.new_name??'终止上市'}</small></th><td>{event.effective_on}<small>{kinds[event.kind]??event.kind}</small></td><td><a href={`${event.source_url}#page=${event.proof_page}`} target="_blank" rel="noreferrer">原PDF第{event.proof_page}页 ↗</a><small>取得 {time(event.observed_at)}</small></td></tr>)}</tbody></table></div>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的ST逐日成交覆盖表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">收盘日</th><th scope="col">成员 / 有成交 / 覆盖</th><th scope="col">停牌或缺失代码</th></tr></thead><tbody>{points.map(point=><tr key={point.date}><th scope="row">{point.date}</th><td>{point.member_count} / {point.observed_members} / {coverage(point.coverage_ratio)}</td><td>{point.missing_symbols.join('、')||'无'}</td></tr>)}</tbody></table></div>
        <p>历史日表首次取得至 {data.source_fetched_at&&time(data.source_fetched_at)}；参考路径生成于 {data.materialized_at&&time(data.materialized_at)}（北京时间）。后续打开页面只核对归档，不会自动采集。</p>
      </details>
    </>}
  </section>
}
