import {useState} from 'react'
import type {RegimeIssuerCheck} from './stRegimeTypes'
const pct=(n:number|null)=>n==null?'缺成交端点':`${n>0?'+':''}${n.toFixed(2)}%`
export function STIssuerCheck({check:c}:{check:RegimeIssuerCheck}){
 const [period,setPeriod]=useState('5')
 return <section className="regime-issuer-check" aria-label={`${c.name}当时风险核验`}>
  <h4>部分账户解冻以后，为什么还不能说风险解除了？</h4>
  <p><strong>{c.name} · {c.symbol}：</strong>{c.answer}</p>
  <p>{c.what_changed}</p>{c.full_window&&<p>后来同窗{c.full_window.anchor} → {c.full_window.through}（{c.full_window.market_days}个市场交易日）：个股{pct(c.full_window.stock_pct)}，大盘{pct(c.full_window.market_pct)}，ST参考{pct(c.full_window.st_pct)}。价格变化不替代上面的风险判断，也不能单归因于这两份公告。</p>}
  <details><summary>看解冻范围、当时风险与同窗行情</summary>
   <p>石岛玻璃三个账户解冻合计{Number(c.released_total_yuan).toLocaleString('zh-CN',{minimumFractionDigits:2})}元。仍被冻结：{c.still_frozen_scope}</p>
   <p>2025年度归母净亏损{Math.abs(Number(c.net_loss_wanyuan)).toLocaleString('zh-CN')}万元，期末净资产{Number(c.net_assets_wanyuan).toLocaleString('zh-CN')}万元；负净资产警示与部分账户改善分开核。</p>
   {c.facts.map((f,n)=><div key={`${f.source.announcement_id}-${n}`}><p>{f.published_on}公开（原件落款{f.document_dated_on}）：{f.text}</p><a href={f.source.url} target="_blank" rel="noreferrer">{f.source.title} · 第{f.source.page}页 ↗</a></div>)}
   <label>公开后看几天 <select aria-label="华鹏公告观察窗口" value={period} onChange={e=>setPeriod(e.target.value)}>{['1','5','20'].map(n=><option key={n} value={n}>{n}个交易日</option>)}</select></label>
   {c.events.map(e=>{const o=e.observation,w=o.windows[period];return <p key={e.event_key}><strong>{e.published_on} · {e.title}</strong><br/>{o.anchor} → {w?.through??'后续不足'}：个股{pct(w?.stock_pct??null)}，大盘{pct(w?.market_pct??null)}，ST参考{pct(w?.st_pct??null)}。</p>})}
   <p>从公开日或之前最近收盘后起算，不认证最早反应；相邻窗口重叠，不算独立经验验证。</p>
   <p><strong>什么证据会更新判断：</strong>{c.what_would_change}</p>
  </details>
  <p className="reading-caption">{c.boundary}</p>
 </section>
}
