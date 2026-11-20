import type {NingkeComparativeFollowup} from './stRegimeTypes'
const yuan=(v:string)=>Number(v).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})+'元'
const label=(key:string)=>key==='assets'?'总资产':'归母权益'
export function STNingkeComparativeFollowup({data}:{data?:NingkeComparativeFollowup|null}){
 if(!data)return null
 return <section id="st-ningke-comparative-followup" aria-label="宁科比较栏续核" style={{scrollMarginTop:80}}>
  <h2>{data.title}</h2><p>{data.answer}</p>
  <h3>这轮新增证据改变了什么？</h3><p>{data.what_changed}</p><p>{data.interpretation}</p>
  <details><summary>并列查看主要指标页、合并表与年度审计原数</summary>
   <table className="regime-table"><caption>均为人民币元；四组上年末比较数均指2025年末，2024年末另作年份排查</caption><thead><tr><th>指标</th><th>半年报主要指标页上年末</th><th>年度审计2025年末</th><th>半年报合并表上年末</th><th>三季报上年末</th><th>年度审计2024年末</th></tr></thead><tbody>{data.comparison_rows.map(r=><tr key={r.metric}><th>{label(r.metric)}</th><td>{yuan(r.h1_summary_prior)}</td><td>{yuan(r.audited_2025)}</td><td>{yuan(r.h1_balance_prior)}</td><td>{yuan(r.q3_prior)}</td><td>{yuan(r.annual_2024)}</td></tr>)}</tbody></table>
   <p>主要指标页两项数值也不等于年度审计的2024年末比较数，暂不支持用简单年份错位解释。</p>
  </details>
  <details><summary>同一个半年末数，换比较基数后意味着什么？</summary>
   <table className="regime-table"><caption>本轮算术复算，不冒充原报告披露的同比或正式更正</caption><thead><tr><th>指标</th><th>2026年半年末</th><th>沿主要指标页基数的变化额</th><th>沿相互印证基数的变化额</th><th>后者变化率</th></tr></thead><tbody>{data.comparison_rows.map(r=><tr key={r.metric}><th>{label(r.metric)}</th><td>{yuan(r.h1_current)}</td><td>{yuan(r.change_using_summary)}</td><td>{yuan(r.change_using_corroborated_balance)}</td><td>{Number(r.recomputed_change_pct).toFixed(2)}%</td></tr>)}</tbody></table>
   <p>归母权益差额与半年归母亏损相等是本轮勾稽结果，不是新增资金的证明。主要指标页差异仍未解释，不能自行改写公司原报。</p>
  </details>
  <h3>还需要什么才能关闭冲突？</h3><ul>{data.watch.map(w=><li key={w}>{w}</li>)}</ul>
  <details><summary>原页、扫描读数与核验限制</summary><p>{data.annual_source_reading}</p>{data.sources.map(s=><p key={s.announcement_id}>{s.title}：{s.selected_pages.map(n=><span key={n}><a href={`${s.url}#page=${n}`} target="_blank" rel="noreferrer">PDF第{n}页</a>{' '}</span>)}</p>)}<p>{data.boundary}</p><p>复用3份原件，核6个关键图像页；没有新增下载或行情，也未把旧目录缺页或诉讼数字差异关闭。</p></details>
 </section>
}
