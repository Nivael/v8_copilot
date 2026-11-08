import {useState} from 'react'
import type {ReactNode} from 'react'
import type {RegimeComparison,STRegimeData} from './stRegimeTypes'
const pct=(v:number|null|undefined)=>v==null?'待核':`${v>0?'+':''}${v.toFixed(2)}%`
const readableFact=(text:string)=>text.replace(/(-?\d+(?:\.\d+)?)元/g,(original,amount:string)=>{const n=Number(amount);return Math.abs(n)>=100000000?`约${(n/100000000).toFixed(2)}亿元`:Math.abs(n)>=10000?`约${(n/10000).toFixed(2)}万元`:original})
const phaseReading=(st:number,market:number)=>st>=0&&market>=0?`均上涨，ST${st>=market?'涨得更多':'涨得较少'}`:st<0&&market<0?`均下跌，ST${st>=market?'跌得较少':'跌得更多'}`:st>=0?'ST上涨，大盘下跌':'ST下跌，大盘上涨'
const topics=[['journey','这几个月发生了什么','先看过程'],['market','大盘影响有多明显','看同向与背离'],['events','公告到底改变了什么','看公司与阶段'],['lessons','下次怎样看得更准','看条件与反例']] as const
export function STRegimeThemes({data,comparison,chart,onEvidence}:{data:STRegimeData;comparison:RegimeComparison;chart:ReactNode;onEvidence:(view:string)=>void}){
 const [topic,setTopic]=useState('journey')
 const [symbol,setSymbol]=useState('603398')
 const [window,setWindow]=useState('5')
 const [showAll,setShowAll]=useState(false)
 const themes=data.themes,ann=themes?.announcements
 const all=data.comparisons.find(c=>c.key==='all')??comparison
 const after=all.after,fixed=all.fixed_after
 const companies=Array.from(new Map((ann?.verified_events??[]).map(e=>[e.symbol,e.name])).entries()).sort((a,b)=>a[0].localeCompare(b[0]))
 const selected=companies.some(([s])=>s===symbol)?symbol:companies[0]?.[0]
 const events=(ann?.verified_events??[]).filter(e=>e.symbol===selected)
 const condition=after.conditions.find(c=>c.key==='down')
 return <div className="regime-topics">
  <p className="regime-topic-intro">想弄清哪件事？选一个问题，先看答案，再核对过程和证据。</p>
  <nav className="regime-topic-nav" aria-label="复盘问题">{topics.map(([key,title,sub],i)=><button type="button" key={key} aria-pressed={topic===key} onClick={()=>setTopic(key)}><small>0{i+1} · {sub}</small><span>{title}</span></button>)}</nav>
  <p className="regime-topic-date">观察期 {after.start} — {data.through} · {after.days} 个交易日 · 11月只到最后完整交易日；不是整月</p>
  {topic==='journey'&&<div className="regime-topic-body">
   <p className="reading-kicker">先看答案</p><h3>{(after.reference_change_pct??0)<0?(after.reference_change_pct??0)>(after.market_change_pct??0)?'整体跌得比大盘少，个股还要分别看':'整体仍在下跌，个股还要分别看':'整体参考回升，个股还要分别看'}</h3>
   <p>完整后窗ST等权参考 {pct(after.reference_change_pct)}，中证全指 {pct(after.market_change_pct)}。固定7月3日的{fixed.total}只股票中，{fixed.covered}只有完整端点，{fixed.positive_pct==null?'上涨覆盖面待核':`其中约${fixed.positive_pct.toFixed(0)}%上涨`}，中位数 {pct(fixed.median_pct)}；另{fixed.missing}只缺口保留。“相对强”与“多数赚钱”是两件事。</p>
   {chart}
   <h4>过程拆开看，结论才不容易被起止点带偏</h4>
   {themes?.months?<div className="regime-scroll" role="region" aria-label="分月行情过程" tabIndex={0}><table className="regime-table"><thead><tr><th>阶段</th><th>ST参考</th><th>大盘</th><th>小盘风格</th><th>怎样理解</th><th>覆盖</th></tr></thead><tbody>{themes.months.map(m=><tr key={m.month}><th>{m.month}<small>{m.start} — {m.through}</small></th><td>{pct(m.st_pct)}</td><td>{pct(m.market_pct)}</td><td>{pct(m.small_pct)}</td><td>{phaseReading(m.st_pct,m.market_pct)}</td><td>{m.days}日</td></tr>)}</tbody></table></div>:<p>本版没有独立分月资料，请展开核对已有窗口。</p>}
   <p className="reading-caption">各月按实际覆盖交易日连乘，7月从6日开始，11月只有首周。各月涨跌幅不能相加；小盘风格使用中证2000。</p>
   <h4>再问：与规则改变之前有什么区别？</h4><p>前后各40日：ST参考从 {pct(comparison.key==='40'?comparison.before.reference_change_pct:data.comparisons.find(c=>c.key==='40')?.before.reference_change_pct)} 到 {pct(data.comparisons.find(c=>c.key==='40')?.after.reference_change_pct)}。完整后窗更长，回答的是后来走了多远；等长窗口才用于前后描述比较。只有一次规则事件，仍无法隔离市场、公告和预期交易的影响。</p>
   <button className="regime-text-link" onClick={()=>onEvidence('规则前后')}>核对等长20/40日、波动与旧5%边界 →</button>
  </div>}
  {topic==='market'&&<div className="regime-topic-body"><p className="reading-kicker">先看答案</p><h3>市场环境不能略过，影响份额仍不能分摊</h3><p>规则后大盘下跌的 {condition?.days} 天，ST参考日均 {pct(condition?.st_mean_pct)}；上涨日的日均表现为 {pct(after.conditions.find(c=>c.key==='up')?.st_mean_pct)}。同向与背离都要保留，不能把某天个股涨跌直接归给公司公告。</p><h4>先挑大盘波动最大的日子，核对ST是否一起动</h4><p>下表按大盘单日涨跌绝对值挑选前8日，再按时间排列。它便于发现市场冲击，不能代替全部交易日的统计。</p><div className="regime-scroll" role="region" aria-label="大盘波动较大交易日" tabIndex={0}><table className="regime-table"><thead><tr><th>日期</th><th>大盘</th><th>ST参考</th><th>当日ST上涨占比</th></tr></thead><tbody>{themes?.market_days.map(d=><tr key={d.date}><th>{d.date}</th><td>{pct(d.market_pct)}</td><td>{pct(d.return_pct)}</td><td>{pct(d.positive_pct)}</td></tr>)}</tbody></table></div><h4>看公告时，用同一窗口作对照</h4><p>先比较个股、主板ST参考与大盘是否同向，再问该公告有没有新增法律、财务或履约事实。相对大盘的差值是观察线索，不能直接解释成公告贡献。</p><button className="regime-text-link" onClick={()=>onEvidence('大盘联动')}>核对全部交易日、相关性与市场涨跌环境 →</button></div>}
  {topic==='events'&&<div className="regime-topic-body"><p className="reading-kicker">先看问题</p><h3>公告发了以后，事情走到了哪一步？</h3><p>同一个“有进展”，可能只是签约，也可能已经付款或完成登记。把阶段串起来，再看随后个股与市场的同期变化，才能分清事实推进与价格表现。</p>
   {ann?<><p className="regime-topic-coverage">目录：{ann.companies}家公司、{ann.catalog_rows.toLocaleString()}条披露。正文选样：{ann.verified_companies}家公司、{ann.verified_documents}份已核文件、{ann.verified_events.length}条事件。正文来自此前已核材料，本轮没有重新逐份读完全部公告。</p><div className="regime-stock-controls"><label>选择公司<select aria-label="公告复盘公司" value={selected??''} onChange={e=>{setSymbol(e.target.value);setShowAll(false)}}>{companies.map(([s,n])=><option key={s} value={s}>{n} · {s}</option>)}</select></label><label>随后观察窗口<select aria-label="公告后观察窗口" value={window} onChange={e=>setWindow(e.target.value)}><option value="1">1个交易日</option><option value="5">5个交易日</option><option value="20">20个交易日</option></select></label></div><p className="reading-caption">从披露日收盘（非交易日取之前最近收盘）起算，随后完整交易日比较；没有精确发布时间，不把这当作最早市场反应。公告日内变化不计入。停牌、缺价与不足窗口保留待核。</p>
   <p className="reading-caption">{showAll?`完整展示本公司${events.length}条已核事件，按时间排列。`:`先看最近${Math.min(5,events.length)}条；早期事件可展开。`}</p><ol className="regime-event-list">{(showAll?events:events.slice(-5)).map(e=>{const w=e.observation.windows[window];return <li key={`${e.id}-${e.source.sha256}`}><p className="reading-kicker">{e.published_on}</p><h4>{e.title}</h4><p>{readableFact(e.change)}</p>{e.date_uncertainty&&<p className="regime-date-conflict"><strong>日期待核：</strong>{e.date_uncertainty}{e.alternate_observation&&<>按另一日期从{e.alternate_observation.anchor}收盘起，至{e.alternate_observation.windows[window].through??'窗口未满'}：个股{pct(e.alternate_observation.windows[window].stock_pct)}、大盘{pct(e.alternate_observation.windows[window].market_pct)}、ST参考{pct(e.alternate_observation.windows[window].st_pct)}。</>}</p>}<p>{e.interpretation}</p><div className="regime-event-returns"><span>个股 <b>{pct(w.stock_pct)}</b></span><span>大盘 <b>{pct(w.market_pct)}</b></span><span>ST参考 <b>{pct(w.st_pct)}</b></span></div><p className="reading-caption">{e.observation.anchor} → {w.through??'后续窗口未满'}{w.gap?` · ${w.gap}`:''}；三者同窗，价格不证明公告因果。</p><details><summary>查看依据与下一步核对</summary><p>{e.evidence_detail}</p><p>事实原数：{e.change}</p><p>继续核对：{e.watch}</p><a href={e.source.url} target="_blank" rel="noreferrer">{e.source.title} · 第{e.source.page}页 ↗</a><p className="reading-caption">原件标识 {e.source.sha256.slice(0,12)}；公司主体范围 {e.entity_scope}。</p></details></li>})}</ol>{events.length>5&&<button className="regime-text-link" onClick={()=>setShowAll(v=>!v)}>{showAll?'收起早期事件':`展开本公司完整${events.length}条事件链 →`}</button>}<p className="reading-caption">{ann.boundary}</p></>:<p>本版尚未绑定公告正文选样；不以标题代替事实。</p>}
  </div>}
  {topic==='lessons'&&<div className="regime-topic-body"><p className="reading-kicker">把逻辑留给下次</p><h3>先查变化，再看相对表现，最后保留反例</h3><div className="regime-lessons">
   <section><h4>① 先确定比较对象</h4><p>看整批行情，用每天当时在场的ST；看原来那批股票，用7月3日固定150只。两者回答不同问题，退市、摘帽与缺价都要留在记录里。</p><p><strong>何时重查：</strong>样本名单变化、停牌或端点缺失时，先检查分母和覆盖，再解释涨跌。</p><button className="regime-text-link" onClick={()=>onEvidence('整批个股')}>查看150只完整名单 →</button></section>
   <section><h4>② “有进展”要落实到履约</h4><p>宝馨竞得、异议重拍、再次竞得和过户是一条有回退的链；沐邦催收、诉讼受理与到账也需要分别核实。一个阶段不能提前代表最终完成。</p><p><strong>可能改变判断的证据：</strong>付款凭据、登记结果、法院裁定或正式终止；事实推进后仍要检查价格是否已经反映预期。</p><button className="regime-text-link" onClick={()=>setTopic('events')}>沿公告链核对 →</button></section>
   <section><h4>③ 市场与公司证据一起看</h4><p>同样的公告，处于普跌和普涨环境时，个股绝对涨跌容易给出不同印象。固定同一窗口比较个股、ST与大盘，保留“事实变好但价格下跌”与“风险仍在但价格上涨”的反例。</p><p><strong>仍不能回答：</strong>没有可比对照与精确时点，不能估计公告或规则各造成多少涨跌，也不能据此预测下次收益。</p></section>
  </div><p className="reading-caption">这些是本轮复盘的核对原则。一次制度变化、重叠窗口和同一公司多条公告不算独立实证，未自动晋级为经验证的交易方法。</p></div>}
 </div>
}
