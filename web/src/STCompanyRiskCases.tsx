import {STSubsidiaryCivil} from './STSubsidiaryCivil'
import {useState} from 'react'
import type {RegimeCompanyRiskCases} from './stRegimeTypes'
const pct=(n:number|null)=>n==null?'端点待核':`${n>0?'+':''}${n.toFixed(2)}%`
const wan=(n:string)=>(Number(n)/10000).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
export function STCompanyRiskCases({data:d}:{data:RegimeCompanyRiskCases|null|undefined}){
 const [period,setPeriod]=useState('5')
 if(!d)return null
 return <section className="regime-company-risk-cases" aria-label="高科与华鹏独立案例对照">
  <h4>同样跌近一半，问题是否相同？</h4><p>{d.answer}</p>
  <p>两份三季报均为2026年1—9月累计、9月末存量，均未经审计；公开日不同，以下资料均截至{d.through}已披露。财务金额单位万元。</p>
  <div className="regime-scroll"><table className="regime-table"><thead><tr><th>公司</th><th>收入同比</th><th>归母利润 · 累计</th><th>经营现金净额 · 累计</th><th>归母净资产 · 期末</th><th>7月3日至截止股价</th></tr></thead><tbody>{d.comparison.map(c=><tr key={c.symbol}><th>{c.name}</th><td>{Number(c.financial.revenue_yoy_pct)>0?'+':''}{c.financial.revenue_yoy_pct}%</td><td>{wan(c.financial.parent_profit)}</td><td>{wan(c.financial.operating_cash)}</td><td>{wan(c.financial.parent_equity)}</td><td>{pct(c.price_window.stock_pct)}</td></tr>)}</tbody></table></div>
  <p>股价比较为同一{d.comparison[0].price_window.market_days}个市场交易日；同窗大盘{pct(d.comparison[0].price_window.market_pct)}、ST参考{pct(d.comparison[0].price_window.st_pct)}。相近跌幅不证明相同原因，也不能由财报单项或收购并表后的收入增速判断风险解除。</p>
  {d.subsidiary_civil&&<STSubsidiaryCivil data={d.subsidiary_civil}/>}<details><summary>核高科的风险链、原件与日期差异</summary>
   <p>{d.what_changed}</p><p>高科原警示：{d.comparison[0].warning_cause}。华鹏原警示：{d.comparison[1].warning_cause}。不从期末净资产的正负反推全部ST成因。</p>
   {d.facts.map((f,n)=><div key={`${f.source.announcement_id}-${n}`}><p>{f.published_on}公开：{f.text}</p><a href={f.source.url} target="_blank" rel="noreferrer">{f.source.title} · 第{f.source.page}页 ↗</a></div>)}
   <p>同期间的华鹏报表来源：<a href={d.comparison[1].financial.source.url} target="_blank" rel="noreferrer">{d.comparison[1].financial.source.title} · 第{d.comparison[1].financial.source.page}页 ↗</a>；两股净资产的原页及更完整范围见各自时间线。</p>
   <p><strong>日期不确定性：</strong>个人立案的官方目录及原件落款为7月15日，<a href={d.media_date_note.url} target="_blank" rel="noreferrer">{d.media_date_note.title} ↗</a>在{d.media_date_note.reported_on} {d.media_date_note.reported_time_local}已有报道。保留两种起算，不认证官方精确最早时刻。</p>
   <label>公告后看几天 <select aria-label="高科风险链观察窗口" value={period} onChange={e=>setPeriod(e.target.value)}>{['1','5','20'].map(n=><option key={n} value={n}>{n}个交易日</option>)}</select></label>
   <ul>{d.events.map(e=>{const w=e.observation.windows[period],a=e.alternate_observation?.windows[period];return <li key={e.event_key}><strong>{e.published_on} · {e.title}</strong>{e.background_only?<p>前置背景早于行情覆盖，不计算窗口。</p>:w?.through?<p>目录日期起算{e.observation.anchor} → {w.through}：个股{pct(w.stock_pct)}，大盘{pct(w.market_pct)}，ST参考{pct(w.st_pct)}。</p>:<p>后续交易日不足，保留空值。</p>}{a?.through&&<p>媒体前夜日期起算{e.alternate_observation?.anchor} → {a.through}：个股{pct(a.stock_pct)}，大盘{pct(a.market_pct)}，ST参考{pct(a.st_pct)}。这是日期敏感性，不是第二次独立验证或公告净贡献。</p>}</li>})}</ul>
   <p><strong>什么证据会改变判断：</strong>{d.what_would_change}</p>{!!d.open_catalog_items?.length&&<p>本轮尚未核正文的控股子公司另案：{d.open_catalog_items.map(x=><span key={x.announcement_id}><a href={x.url} target="_blank" rel="noreferrer">{x.announcement_date} · {x.title} ↗</a>；</span>)}标题不代替程序结论，本项撤销不外推全部子公司案件。</p>}
  </details>
  <p><strong>可保留的条件提示：</strong>{d.conditional_experience}</p><p className="reading-caption">{d.experience_status} {d.boundary}</p>
 </section>
}
