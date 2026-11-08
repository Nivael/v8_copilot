import {useState} from 'react'
import type {RegimeStrongRemovalCases,StrongCaseReport,LabelSourceFact} from './stRegimeTypes'
type LabelSource=LabelSourceFact['source']
const pct=(n:number|null)=>n==null?'缺实际成交端点':(n>0?'+':'')+n.toFixed(2)+'%'
const money=(n:string)=>(Number(n)/10000).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
const metrics=[['revenue','营业收入'],['parent_profit','归母净利润'],['deducted_profit','扣非净利润'],['operating_cash','经营现金净额'],['parent_equity','期末归母净资产']] as const
function Source({source:s}:{source:LabelSource}){return <a href={s.url+'#page='+s.page} target="_blank" rel="noreferrer">原件第{s.page}页 ↗</a>}
function Reports({reports}:{reports:{label:string;value:StrongCaseReport}[]}){return <div className="regime-scroll"><table className="regime-table"><caption>金额：万元；利润与现金净额负号表示亏损或流出，净资产为期末存量</caption><thead><tr><th>指标</th>{reports.map(x=><th key={x.label}>{x.label}<small>披露{x.value.published_on}</small></th>)}</tr></thead><tbody>{metrics.map(([k,label])=><tr key={k}><th scope="row">{label}</th>{reports.map(x=><td key={x.label}>{money(x.value[k])} <Source source={x.value.metric_sources[k]}/></td>)}</tr>)}</tbody></table></div>}
export function STStrongRemovalCases({data:d}:{data:RegimeStrongRemovalCases|null|undefined}){
 const [period,setPeriod]=useState('5')
 if(!d)return null
 return <section id="st-strong-removal-cases" style={{scrollMarginTop:80}} className="regime-removal-cohort" aria-label="强势摘帽案例与经营变化">
 <h4>摘帽后涨得强，经营就已经修复了吗？</h4><p>{d.answer}</p>
 <p>这两个案例帮助解释“平均涨、但多数跌”：12只摘帽股后5日均值{pct(d.cohort5.after.mean_pct)}，中位数{pct(d.cohort5.after.median_pct)}，只有{d.cohort5.after.positive_count}只上涨。神雾、东晶是其中的强势路径；它们的表现不代表全部ST。</p>
 <label>检验强势持续多久 <select aria-label="强势案例行情窗口" value={period} onChange={e=>setPeriod(e.target.value)}>{['5','20','40'].map(n=><option key={n} value={n}>摘帽前收盘起，后{n}个市场日</option>)}</select></label>
 <div className="regime-scroll"><table className="regime-table"><caption>每行使用该股同日期的大盘与ST参考；不同公司起止日期不同</caption><thead><tr><th>公司与日期</th><th>个股</th><th>同窗大盘</th><th>同窗ST</th><th>另看7月3日至11月6日个股</th></tr></thead><tbody>{d.rows.map(r=>{const w=r.windows[period].after;return <tr key={r.symbol}><th scope="row">{r.name}<small>{w.anchor} → {w.through}</small></th><td>{pct(w.stock_pct)}</td><td>{pct(w.market_pct)}</td><td>{pct(w.st_pct)}</td><td>{pct(r.full.stock_pct)}</td></tr>})}</tbody></table></div>
 <p>两股后40日仍上涨，但完整7月至11月均为下跌。“摘帽后短窗强”与“这几个月赚钱”不是同一结论；同窗跑赢大盘也不能证明摘帽的净贡献。</p>
 <h5>先看截至三季报的结果，再追溯当时知道什么</h5>
 <Reports reports={d.rows.map(r=>({label:r.name+' · 前三季',value:r.third}))}/>
 {d.rows.map(r=><details key={r.symbol}><summary>{r.name}：改善在哪里，约束还在哪里？</summary>
  <p>{r.answer}</p><p>第三季单季经营现金净额（前三季减上半年）为{money(r.single_quarter.operating_cash)}万元，已转正；前三季累计仍为{money(r.third.operating_cash)}万元。单季归母{money(r.single_quarter.parent_profit)}万元、扣非{money(r.single_quarter.deducted_profit)}万元，仍亏损。</p>
  <Reports reports={[{label:'上半年'+(r.correction?'（更正后）':''),value:r.half},{label:'前三季',value:r.third}]}/>
  <p>现金余额也另核：期初{money(r.cash.opening)}万元，经营{money(r.cash.operating)}、投资{money(r.cash.investing)}、筹资{money(r.cash.financing)}、汇率{money(r.cash.fx)}万元，合计变化{money(r.cash.change)}万元，期末现金及现金等价物{money(r.cash.closing)}万元。它不同于利润或经营现金净额。 <Source source={r.cash.source}/></p>
  <h5>当时已知与后来更新</h5><p>摘帽公告{r.removal.announced_on}，{r.removal.effective_on}生效，日涨跌幅仍10%。半年实际披露{r.correction?.original.published_on??r.half.published_on}，三季披露{r.third.published_on}；两份实际财报都晚于摘帽，不回填为7月已知。{r.correction&&'半年更正直到10月29日才可知。'}</p>
  {r.removal.facts.map((f,n)=><p key={'removal'+n}>{f.text} <Source source={f.source}/></p>)}
  {r.facts.map((f,n)=><p key={n}>{f.text} <Source source={f.source}/></p>)}
  {r.correction&&<details><summary>东晶半年更正：哪些数字变了，哪些没变？</summary><p>{r.correction.reason}</p><Reports reports={[{label:'8月25日原披露',value:r.correction.original},{label:'10月29日更正后',value:r.half}]}/><p>收入增加{money(r.correction.delta.revenue)}万元、扣非亏损减少{money(r.correction.delta.deducted_profit)}万元；归母、经营现金和净资产未改。不能把同一报告更正算第二次独立改善。 <Source source={r.correction.source}/></p><p>若错用旧半年扣非去减前三季，会得到第三季扣非{money(r.correction.incorrect_q3_from_old_half)}万元；按更正后同口径应为{money(r.single_quarter.deducted_profit)}万元，与三季报单季表一致。旧版保留用于还原当时信息，不混用于当前单季计算。</p></details>}
  <p className="reading-caption">三季报未经审计；半年本轮只核摘要，不由“非标准意见不适用”推定审计状态。</p><p><strong>什么会改变判断：</strong>{r.what_would_change}</p>
 </details>)}
 <p><strong>可保留的条件性经验：</strong>先把状态解除、收入扩张、扣非盈利、现金回流拆开核实，再用后续原件更新。收入增长与短期上涨都不能替代另外几项；这一轮仅补足两个案例的反例边界，未晋级通用规律。</p>
 <details><summary>选样与解释限制</summary><p>{d.selection}</p><p>{d.boundary}</p><p>{d.what_would_change}</p></details>
 </section>
}
