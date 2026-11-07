import {useState} from 'react'
import type {MarketRiskIndex,SSESTNoticeReview,STReconstruction as Reference} from './types'

const labels={all:'沪深ST重建',SSE:'沪市ST重建',SZSE:'深市已核样本'}
const pct=(v:number|null|undefined)=>v==null?'—':`${v>0?'+':''}${v.toFixed(2)}%`
const coverage=(v:number|undefined)=>v==null?'—':`${(v*100).toFixed(2)}%`
const time=(s:string|undefined)=>s?new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未取得'
const triage:Record<string,string>={effective_transition_with_primary_date_clause:'另有生效日期原文',application_only_title:'申请标题，未作生效',layered_warning_title:'叠加警示标题',progress_or_continuation_title:'进展或继续警示标题'}

export function STReconstruction({data,indices,noticeReview}:{data:Reference;indices:MarketRiskIndex[];noticeReview?:SSESTNoticeReview}){
  const [group,setGroup]=useState<'all'|'SSE'|'SZSE'>('all')
  const [position,setPosition]=useState<number|null>(null)
  const points=data.points
  const noticeReviewed=noticeReview?.availability==='reviewed'&&noticeReview.review_scope==='security_identity_and_member_status_clauses_only'
    &&noticeReview.items.length>0&&noticeReview.reviewed_items===noticeReview.items.length&&noticeReview.through===data.through&&noticeReview.items.length===data.catalog?.items.length
    &&noticeReview.items.length===noticeReview.catalog_items&&noticeReview.items.every((r,i)=>r.symbol===data.catalog?.items[i].symbol&&r.published_on===data.catalog?.items[i].published_on)
  const ready=data.availability==='reconstructed'&&points.length>=2&&points[0].date===data.start&&points.at(-1)?.date===data.through
    &&points.every((p,i)=>(i===0||p.date>points[i-1].date)&&(['all','SSE','SZSE'] as const).every(g=>p[g].close!=null&&Number.isFinite(p[g].close)
      &&p[g].close!>0&&p[g].coverage_ratio>=(data.coverage_threshold??1)))
  const index=Math.min(position??points.length-1,points.length-1)
  const selected=points[index]
  const market=indices.find(r=>r.code==='000985.CSI'&&!r.historical_only&&r.through===data.through)
  const marketPath=market?.path.filter(p=>data.start!=null&&data.through!=null&&p.date>=data.start&&p.date<=data.through)??[]
  const matched=ready&&marketPath.length===points.length&&marketPath.every((p,i)=>p.date===points[i].date&&p.close!=null&&Number.isFinite(p.close)&&p.close>0)
  const values=ready?points.map(p=>p[group].close!/points[0][group].close!*100):[]
  const broad=matched?marketPath.map(p=>p.close!/marketPath[0].close!*100):[]
  const lo=Math.floor(Math.min(100,...values,...broad)/5)*5-2,hi=Math.ceil(Math.max(100,...values,...broad)/5)*5+2
  const x=(i:number)=>80+i*728/(points.length-1),y=(v:number)=>216-(v-lo)/(hi-lo)*190
  const path=(v:number[])=>v.map((n,i)=>`${i===0?'M':'L'}${x(i).toFixed(2)},${y(n).toFixed(2)}`).join(' ')
  const metric=data.metrics?.[group]
  return <section className="learning-freshness" aria-label="沪深ST重建参考">
    <header className="learning-section-head"><div><p className="eyebrow">风格参考 / 成员重建</p><h2>沪深ST重建参考</h2></div><span>沪市逐日成员待独立核验</span></header>
    <p><strong>{ready?'价格来源覆盖沪深两所，完整ST核验尚未通过。':'重建参考当前不可用，完整ST核验尚未通过。'}</strong> 沪市按日期快照及生效公告重建，目录筛查和期末相符不能证明中间没有遗漏。参考路径保留这一限制，不能据此设置风险权重。</p>
    {noticeReviewed&&<p>补充核对已覆盖这 {noticeReview?.reviewed_items} 项公告的身份及成员状态条款，原文页见下方“沪市ST公告原文条款核对”。这仍不等同逐日名单已核验。</p>}
    {!ready?<p>来源或任一日、任一交易所的成交覆盖未通过，整段参考路径暂不发布，不展示缩短后的成功窗口。</p>:<>
      <p>{data.start} 至 {data.through}，{points.length}个收盘点。沪市起始 {data.sse_anchor_members} 只，期间共 {data.sse_distinct_members} 只、期末 {data.sse_endpoint_members} 只；深市期间共 {data.szse_distinct_members} 只、期末 {data.szse_endpoint_members} 只。</p>
      <label>查看范围 <select aria-label="ST重建查看范围" value={group} onChange={e=>setGroup(e.target.value as typeof group)}>{(Object.keys(labels) as Array<keyof typeof labels>).map(g=><option key={g} value={g}>{labels[g]}</option>)}</select></label>
      <div className="market-recent-grid"><article><span>{labels[group]} · 窗口参考变化</span><strong>{pct(metric?.return_pct)}</strong><small>首个收盘点归一为100</small></article><article><span>窗口最大回撤</span><strong>{pct(metric?.max_drawdown_pct)}</strong><small>描述性参考路径，不是组合财富</small></article><article><span>最低每日成交覆盖</span><strong>{coverage(metric?.minimum_coverage)}</strong><small>每所、每日均须通过 {coverage(data.coverage_threshold)} 门槛</small></article></div>
      <div className="market-risk-legend"><span><i/>{labels[group]}</span>{matched&&<span><i className="market-line-1"/>中证全指 · 同窗</span>}</div>
      <svg className="market-st-chart" viewBox="0 0 840 250" role="img" aria-label={`${labels[group]}${matched?'与同窗中证全指':''}价格参考路径`}>
        <title>成员待完整核验的ST重建参考，首个收盘点为100</title>
        {[lo,(lo+hi)/2,hi].map(tick=><g key={tick}><line x1="80" x2="808" y1={y(tick)} y2={y(tick)} stroke="#e2e9df"/><text x="70" y={y(tick)+4} textAnchor="end">{Number.isInteger(tick)?tick.toFixed(0):tick.toFixed(1)}</text></g>)}
        <line x1="80" x2="808" y1={y(100)} y2={y(100)} stroke="#aab8aa" strokeDasharray="4 4"/>
        <path d={path(values)} stroke="#3d684d"/>{matched&&<path d={path(broad)} stroke="#a47845"/>}
        <line x1={x(index)} x2={x(index)} y1="20" y2="216" stroke="#788d7b" strokeDasharray="3 3"/>
        <circle cx={x(index)} cy={y(values[index])} r="4" fill="#3d684d"/>
        {[0,Math.floor((points.length-1)/2),points.length-1].map(i=><text key={i} x={x(i)} y="240" textAnchor={i===0?'start':i===points.length-1?'end':'middle'}>{points[i].date}</text>)}
      </svg>
      {!matched&&<p>中证全指日期不完全一致，未叠加市场对照线。</p>}
      <label className="market-st-slider">逐日查看 <input type="range" min="0" max={points.length-1} value={index} aria-label="ST重建观察日期" aria-valuetext={selected.date} onChange={e=>setPosition(Number(e.target.value))}/></label>
      <div className="market-st-readout" aria-live="polite"><strong>{selected.date}</strong><span>{labels[group]} {values[index].toFixed(2)}{matched&&` · 中证全指 ${broad[index].toFixed(2)}`}</span><span>成员 {selected[group].member_count} · 有成交 {selected[group].observed_members} · 覆盖 {coverage(selected[group].coverage_ratio)}</span><span>停牌或无成交：{selected[group].missing_symbols.join('、')||'无'}</span></div>
      <p>{data.note}</p>
      <details className="market-source-notes"><summary>沪市成员生效依据、目录筛查与每日分母</summary>
        <p>沪市{data.sse_reviewed_transitions}处生效事项分别核对原公告日期角色及名称方向。{noticeReviewed?<>这{data.catalog?.items.length}项目录已另补身份和成员状态条款核对，下方保留最初标题筛查记录；补充核对不代表正文全部语义或逐日法定名单已核验。</>:<>{data.catalog?.items.length}条目录只做标题筛查，其中申请、进展和叠加警示不直接当作成员增减；未声称目录正文已全部核验，也没有逐日法定名单证明。</>}深市另有{data.szse_reviewed_transitions}处公告及每日完整日表交叉核对。</p>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的沪市ST生效依据表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">证券 / 名称变化</th><th scope="col">生效日</th><th scope="col">原文页 / 取得日</th></tr></thead><tbody>{data.events?.map(e=><tr key={e.symbol+e.effective_on}><th scope="row">{e.symbol}<small>{e.old_name} → {e.new_name}</small></th><td>{e.effective_on}<small>发布 {e.published_on}</small></td><td><a href={`${e.source_url}#page=${e.proof_page}`} target="_blank" rel="noreferrer">原PDF第{e.proof_page}页 ↗</a><small>{time(e.observed_at)}</small></td></tr>)}</tbody></table></div>
        <details><summary>查看目录的{data.catalog?.items.length}条标题筛查</summary><div className="learning-table-wrap" role="region" aria-label="可滚动的风险警示目录筛查表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">证券 / 发布日</th><th scope="col">原标题</th><th scope="col">仅标题层筛查</th></tr></thead><tbody>{data.catalog?.items.map((r,i)=><tr key={i}><th scope="row">{r.symbol}<small>{r.published_on}</small></th><td><a href={r.catalog_url} target="_blank" rel="noreferrer">{r.title} ↗</a></td><td>{triage[r.triage]||r.triage}</td></tr>)}</tbody></table></div></details>
        <div className="learning-table-wrap" role="region" aria-label="可滚动的ST重建逐日分母表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">日期</th><th scope="col">沪深 成员 / 成交 / 覆盖</th><th scope="col">沪市 成员 / 成交 / 覆盖</th><th scope="col">深市 成员 / 成交 / 覆盖</th></tr></thead><tbody>{points.map(p=><tr key={p.date}><th scope="row">{p.date}</th>{(['all','SSE','SZSE'] as const).map(g=><td key={g}>{p[g].member_count} / {p[g].observed_members} / {coverage(p[g].coverage_ratio)}<small>{p[g].missing_symbols.join('、')||'无缺失或停牌'}</small></td>)}</tr>)}</tbody></table></div>
        <details><summary>查看逐日成员代码</summary><div className="learning-table-wrap" role="region" aria-label="可滚动的ST重建每日成员表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">日期</th><th scope="col">沪市重建代码</th><th scope="col">深市已核代码</th></tr></thead><tbody>{data.memberships?.map(p=><tr key={p.date}><th scope="row">{p.date}</th><td>{p.SSE.join('、')}</td><td>{p.SZSE.join('、')}</td></tr>)}</tbody></table></div></details>
        <p>价格原件取得至：沪市 {time(data.sse_price_fetched_at)}，深市 {time(data.szse_price_fetched_at)}；三份沪市公告最后取得 {time(data.newest_notice_observed_at)}；本次生成 {time(data.materialized_at)}（北京时间）。期末另与读取于 {data.endpoint_list_observed_on} 的交易所名单比对，读取日不回填为历史名单日期。</p>
      </details>
    </>}
  </section>
}
