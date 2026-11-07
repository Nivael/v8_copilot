import {useState} from 'react'
import type {CombinedBreadthHistory as History} from './types'

const groups=[{key:'all',label:'沪深A股',color:'#3d684d'},{key:'SSE',label:'沪市A股',color:'#a47845'},{key:'SZSE',label:'深市A股',color:'#7e8b91'}] as const
const num=(n:number|undefined)=>n==null?'—':n.toLocaleString('zh-CN')
const pct=(n:number|null|undefined)=>n==null?'—':`${n.toFixed(2)}%`
const time=(s:string|undefined)=>s?new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未取得'

export function CombinedBreadthHistory({data}:{data:History}){
  const [position,setPosition]=useState<number|null>(null)
  const points=data.points
  const ready=data.availability==='observed'&&data.complete_market_history&&points.length>=2
    &&points.length===data.expected_days&&points[0].date===data.start&&points.at(-1)?.date===data.through
    &&points.every((p,i)=>(i===0||p.date>points[i-1].date)&&groups.every(g=>p[g.key].declining_share_pct!=null
      &&Number.isFinite(p[g.key].declining_share_pct)&&p[g.key].declining_share_pct!>=0&&p[g.key].declining_share_pct!<=100))
  const index=Math.min(position??points.length-1,points.length-1)
  const selected=points[index]
  const x=(i:number)=>80+i*728/(points.length-1)
  const y=(value:number)=>216-value*1.9
  return <section className="learning-freshness" aria-label="沪深历史涨跌分布">
    <header className="learning-section-head"><div><p className="eyebrow">市场宽度 / 两所同窗核对</p><h2>沪深历史涨跌分布</h2></div><span>{ready?'交易所覆盖 2/2':'完整历史窗待核对'}</span></header>
    {!ready?<p>完整沪深历史窗尚未通过核对，暂不展示合并曲线；深市已有原日表可在下方独立查看。缺失不会解释为低风险。</p>:<>
      <p>{data.start} 至 {data.through}，完整核对 {points.length} 个收盘日、{num(data.observation_count)} 股票日，其中 {num(data.traded_observation_count)} 条有成交记录。</p>
      {data.matches_market_target===false&&<p>本历史窗与当前市场目标日期不同，保留自己的实际截止日。</p>}
      <div className="market-risk-legend">{groups.map(g=><span key={g.key}><i style={{background:g.color}}/>{g.label} · 下跌占有成交股票</span>)}</div>
      <svg className="market-st-chart" viewBox="0 0 840 250" role="img" aria-label="沪深及两所每日下跌股票比例路径">
        <title>下跌股票占当日有成交股票的比例，0至100%</title>
        {[0,25,50,75,100].map(tick=><g key={tick}><line x1="80" x2="808" y1={y(tick)} y2={y(tick)} stroke="#e2e9df"/><text x="70" y={y(tick)+4} textAnchor="end">{tick}%</text></g>)}
        {groups.map(g=><path key={g.key} d={points.map((p,i)=>`${i===0?'M':'L'}${x(i).toFixed(2)},${y(p[g.key].declining_share_pct!).toFixed(2)}`).join(' ')} stroke={g.color}/>)}
        <line x1={x(index)} x2={x(index)} y1="20" y2="216" stroke="#788d7b" strokeDasharray="3 3"/>
        {groups.map(g=><circle key={g.key} cx={x(index)} cy={y(selected[g.key].declining_share_pct!)} r="3.5" fill={g.color}/>)}
        {[0,Math.floor((points.length-1)/2),points.length-1].map(i=><text key={i} x={x(i)} y="240" textAnchor={i===0?'start':i===points.length-1?'end':'middle'}>{points[i].date}</text>)}
      </svg>
      <label className="market-st-slider">逐日查看 <input type="range" min="0" max={points.length-1} value={index} aria-label="市场宽度观察日期" aria-valuetext={selected.date} onChange={e=>setPosition(Number(e.target.value))}/></label>
      <div className="market-st-readout" aria-live="polite"><strong>{selected.date}</strong>{groups.map(g=><span key={g.key}>{g.label}：下跌 {pct(selected[g.key].declining_share_pct)} · 有成交 {num(selected[g.key].observed_trading_stocks)} · 无成交 {num(selected[g.key].nontrading_stocks)}</span>)}</div>
      <p>{data.note}</p>
      <details className="market-source-notes"><summary>逐日数量与停牌依据</summary>
        <p>沪市 {data.sse_suspensions?.ordinary_A_records} 条停牌登记恰好解释 {num(data.sse_suspensions?data.sse_suspensions.notice_confirmed_days+data.sse_suspensions.additional_continuous_days:undefined)} 个未返回股票日，原有公告依据覆盖 {data.sse_suspensions?.notice_confirmed_days} 日，现行接口的连续停牌记录补齐另外 {data.sse_suspensions?.additional_continuous_days} 日。空终止日表示本次观测仍持续，不填作复牌日期；期内终止上市者按实际挂牌结束日退出分母。</p>
        <p className="learning-footnote market-recheck-scroll-hint">左右滑动可查看每日分母、涨跌数量和全部停牌区间。</p>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的沪深每日宽度核对表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">收盘日 / 市场</th><th scope="col">挂牌 / 有成交 / 无成交</th><th scope="col">上涨 / 下跌 / 平盘</th><th scope="col">下跌比例 / 跌幅≥5%家数</th></tr></thead><tbody>{points.flatMap(p=>groups.map(g=><tr key={p.date+g.key}><th scope="row">{p.date}<small>{g.label}</small></th><td>{num(p[g.key].listed_source_stocks)} / {num(p[g.key].observed_trading_stocks)} / {num(p[g.key].nontrading_stocks)}</td><td>{num(p[g.key].advancing)} / {num(p[g.key].declining)} / {num(p[g.key].flat)}</td><td>{pct(p[g.key].declining_share_pct)} / {num(p[g.key].declining_5pct_or_more)}</td></tr>))}</tbody></table></div>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的沪市停牌登记表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">证券 / 登记简称</th><th scope="col">停牌开始 / 最后停牌日</th><th scope="col">区间类型 / 本窗天数</th><th scope="col">停牌及结束原因</th></tr></thead><tbody>{data.sse_suspensions?.records.map((r,i)=><tr key={i}><th scope="row">{r.symbol}<small>{r.name_as_reported}</small></th><td>{r.start_on}<small>{r.last_suspended_on??'观测时仍持续'}</small></td><td>{r.kind==='continuous'?'连续停牌':'全天停牌'} / {r.window_days.length}日</td><td>{r.reason}<small>{r.end_reason||'未登记结束原因'}</small></td></tr>)}</tbody></table></div>
        <p><a href={data.source_url} target="_blank" rel="noreferrer">上交所停复牌登记 ↗</a> · <a href="https://www.szse.cn/market/trend/index.html" target="_blank" rel="noreferrer">深交所历史日表 ↗</a></p>
        <p>价格原件取得至：沪市 {time(data.sse_price_fetched_at)}，深市 {time(data.szse_fetched_at)}；停牌登记及接口定义取得至 {time(data.fetched_at)}；本次生成 {time(data.materialized_at)}（北京时间）。GET仅复核归档，不自动联网更新。</p>
      </details>
    </>}
  </section>
}
