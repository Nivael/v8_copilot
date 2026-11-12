import type {BroadFundEvidence} from './readingTypes'
import {percent} from './readingFormat'

const shares=(value?:string)=>value==null?'—':`${(Number(value)/1e8).toFixed(2)}亿份`

export function BroadFundEvidenceSection({data}:{data:BroadFundEvidence}){
  const nav=data.unit_nav,holders=data.holders
  if(nav.availability!=='available'&&holders.availability!=='available')return null
  return <section className="reading-capital-actions reading-fund-evidence" aria-label="宽基ETF净值与披露持有人">
    {nav.availability==='available'&&<>{nav.headline&&<h3>{nav.headline}</h3>}<p>{nav.interpretation}</p><details className="reading-disclosure"><summary>净值已补至{nav.as_of} · {nav.observed_funds}/{nav.sample_funds}只宽基样本</summary>
      {nav.basis_note&&<p>{nav.basis_note}</p>}<p>每只已核对{nav.sessions}个交易日。下表比较单位净值与份额的同窗变化。</p>
      <div className="reading-scroll"><table><thead><tr><th>ETF</th><th>每份净值</th><th>近5日净值</th><th>近5日份额</th><th>近20日净值</th></tr></thead><tbody>{nav.rows?.map(row=><tr key={row.code}><th>{row.name}<small>{row.code}</small></th><td>{row.unit_nav}元</td><td>{percent(row.five_day_nav_change_pct)}</td><td>{percent(row.five_day_share_change_pct)}</td><td>{percent(row.twenty_day_nav_change_pct)}</td></tr>)}</tbody></table></div>
      <details className="reading-disclosure"><summary>比较日期与各基金原始净值</summary>{nav.rows?.map(row=><p key={row.code}><a href={row.source_url} target="_blank" rel="noreferrer">{row.name} · {row.source_label} ↗</a>；5日从{row.five_day_nav_anchor}、20日从{row.twenty_day_nav_anchor}比较至{row.as_of}。</p>)}{nav.fetched_at&&<p>本次取得于 {new Date(nav.fetched_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}（北京时间）。</p>}</details>
    </details></>}
    {holders.availability==='available'&&<><h3>{holders.headline}</h3><p>{holders.interpretation}</p><details className="reading-disclosure"><summary>哪些基金在增加持有 · 三季报原文</summary>
      <p>持有份额对照 {holders.period_start} 至 {holders.period_end}。此处核对{holders.rows?.length}只基金的季度披露。</p>
      <div className="reading-scroll"><table><thead><tr><th>ETF</th><th>披露的持有人</th><th>期初 → 期末</th><th>持有变化</th></tr></thead><tbody>{holders.rows?.map(row=><tr key={row.code}><th>{row.name}<small>{row.code}</small></th>{row.kind==='feeder_fund'?<><td>联接基金<small>期末占比 {row.closing_share_pct}%</small></td><td>{shares(row.opening_shares)} → {shares(row.closing_shares)}</td><td>{Number(row.holding_change_shares)>0?'+':''}{shares(row.holding_change_shares)}</td></>:<td colSpan={3}>报告期内未出现达到20%披露阈值的单一投资者</td>}</tr>)}</tbody></table></div>
      <p>{holders.scope_note}</p><details className="reading-disclosure"><summary>精确份额与报告页码</summary>{holders.rows?.map(row=><div key={row.code}><strong>{row.name}</strong>{row.kind==='feeder_fund'&&<p>{row.holder_label}：期初 {row.opening_shares} 份，期末 {row.closing_shares} 份；持有变化 {row.holding_change_shares} 份。</p>}{row.sources.map(source=><p key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a></p>)}</div>)}</details>
    </details></>}
  </section>
}
