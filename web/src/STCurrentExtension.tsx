import type {EndpointSelectionAudit} from './STEndpointSelectionAudit'
import {STWeilingStageCheck} from './STWeilingStageCheck'
import type {WeilingStageCheck} from './STWeilingStageCheck'
import {useState} from 'react'
import type {RegimeComparison,RegimeFixed,RegimePeriod} from './stRegimeTypes'

type CurrentEvent={id:string;symbol:string;name:string;published_on:string;document_dated_on:string|null;title:string;change:string;pages:number[];watch:string;source:{url:string;title:string;sha256:string}}
export type CurrentExtension={path?:{date:string;market:number}[];stage_followup?:WeilingStageCheck|null;baseline_through:string;through:string;latest:RegimePeriod;fixed:RegimeFixed;full_comparison:RegimeComparison;tracked:{symbol:string;name:string;still_st:boolean;in_main_board_reference:boolean;anchor:string;through:string;close:number;change_pct:number;events:CurrentEvent[]}[];events:CurrentEvent[];source_counts:{new_pdf_files:number;new_pdf_pages:number;catalog_companies:number;catalog_rows:number};boundary:string}
const pct=(n:number|null)=>n==null?'缺价，保留空值':`${n>0?'+':''}${n.toFixed(2)}%`
export default function STCurrentExtension({data:d,followup,endpointAvailable,audit,onEndpointAudit}:{data?:CurrentExtension|null;followup?:WeilingStageCheck|null;endpointAvailable?:boolean;audit?:EndpointSelectionAudit|null;onEndpointAudit?:()=>void}){
 const [symbol,setSymbol]=useState('603398.SH')
 const [all,setAll]=useState(false)
 if(!d)return null
 const stock=d.tracked.find(s=>s.symbol===symbol)??d.tracked[0]
 const full=d.full_comparison.after
 const positive=d.fixed.rows.filter(r=>r.return_pct!=null&&r.return_pct>0).length
 const rows=all?d.fixed.rows:d.fixed.rows.filter(r=>r.return_pct==null)
 return <section id="st-current-extension" className="regime-topic-body" aria-label="截至11月19日的判断更新">
  <p className="reading-kicker">判断更新 · 行情截至{d.through}</p>
  <h3>最近9日，ST比大盘跌得更深</h3>
  <p>从11月6日收盘到19日，主板动态ST参考{pct(d.latest.reference_change_pct)}，中证全指{pct(d.latest.market_change_pct)}。固定150只原始样本中，{d.fixed.covered}只可比较，只有{positive}只上涨，中位数{pct(d.fixed.median_pct)}。</p>
  {audit&&<p>完整区间146家两端有成交，其中只有141家跨渠道核价通过；5家起点报价差异保留。下方全段中位数改列141家通过核价的子样本，原146家主源数值在核验说明中保留。<button type="button" className="regime-text-link" onClick={onEndpointAudit}>核对报价差异、退出与全部150家 →</button></p>}
  <p>把窗口拉回7月制度变化后，ST全段仍相对少跌。两段观察放在一起，说明此前的相对抗跌没有延续为近期优势；相对少跌也不意味着多数股票上涨。</p>
  <details><summary>比较最近9日与7月以来全段</summary>
   <div className="regime-scroll"><table className="regime-table" aria-label="新旧窗口的相对表现"><thead><tr><th>观察窗口</th><th>动态ST参考</th><th>中证全指</th><th>中证2000</th><th>{audit?'核价通过子样本中位数':'固定150只中位数'}</th></tr></thead><tbody>{[[`11月9—19日 · ${d.latest.days}日`,d.latest,d.fixed],[`7月6日—11月19日 · ${full.days}日`,full,d.full_comparison.fixed_after]].map(([label,p,f])=>{const period=p as RegimePeriod;const fixed=f as RegimeFixed;return <tr key={label as string}><th>{label as string}</th><td>{pct(period.reference_change_pct)}</td><td>{pct(period.market_change_pct)}</td><td>{pct(period.small_cap_change_pct)}</td><td>{pct(audit?Number(audit.windows.find(w=>w.key===(fixed.anchor==='2026-07-03'?'full':'recent'))!.summary.verified_subset_median_pct):fixed.median_pct)}<small>{audit?`${audit.windows.find(w=>w.key===(fixed.anchor==='2026-07-03'?'full':'recent'))!.summary.verified_paired}/${fixed.total}只核价通过`:`${fixed.covered}/${fixed.total}只可比`}</small></td></tr>})}</tbody></table></div>
   <p>ST参考每天按当时在场的主板ST股票等权，再复合逐日收益；固定样本从7月3日的150只出发，离开ST后仍保留。两者回答不同问题。下方原有复盘仍截至{d.baseline_through}，本节单独延伸到{d.through}。</p>
  </details>
  <details><summary>这9日，大盘下跌时ST表现怎样？</summary><table className="regime-table" aria-label="近期市场涨跌环境"><thead><tr><th>市场环境</th><th>天数</th><th>大盘日均</th><th>ST日均</th><th>ST上涨占比日均</th></tr></thead><tbody>{d.latest.conditions.filter(c=>c.key==='up'||c.key==='down').map(c=><tr key={c.key}><th>{c.label}</th><td>{c.days}</td><td>{pct(c.market_mean_pct)}</td><td>{pct(c.st_mean_pct)}</td><td>{pct(c.positive_breadth_pct)}</td></tr>)}</tbody></table><p>这只是9日的条件分组。市场与ST一起下跌是观察结果，仍不能把个股跌幅分摊为市场、公告或制度各自的贡献。</p></details>
  <h4>重点公司的事实与价格，是否朝同一方向？</h4>
  <p>四只持续跟踪股与宝馨比较案例使用同一个收盘起点。思科瑞摘帽后继续保留，科创板股票不计入主板ST参考。</p>
  <table className="regime-table" aria-label="重点公司近期同窗表现"><thead><tr><th>公司</th><th>11月19日收盘</th><th>11月6日收盘以来</th><th>跟踪范围</th></tr></thead><tbody>{d.tracked.map(s=><tr key={s.symbol}><th>{s.name}</th><td>{s.close.toFixed(2)}元</td><td>{pct(s.change_pct)}</td><td>{s.symbol==='002514.SZ'?'比较案例':s.in_main_board_reference?'持续跟踪':'持续跟踪 · 科创板'}{!s.still_st&&' · 已离开ST'}</td></tr>)}</tbody></table>
  <label>选择公司，查看判断依据 <select value={symbol} onChange={e=>setSymbol(e.target.value)}>{d.tracked.map(s=><option key={s.symbol} value={s.symbol}>{s.name}</option>)}</select></label>
  {stock.symbol==='002667.SZ'&&<STWeilingStageCheck data={followup}/>}
  {stock.events.map(e=><article key={e.id}><p className="reading-kicker">{e.published_on}披露</p><h4>{e.title}</h4><p>{e.change}</p><details><summary>依据与下一步核对</summary><p>继续核对：{e.watch}</p><p>文件落款：{e.document_dated_on??'本件未核得确切落款日期'}。</p>{e.pages.map(page=><p key={page}><a href={e.source.url+'#page='+page} target="_blank" rel="noreferrer">{e.source.title} · 第{page}页 ↗</a></p>)}</details></article>)}
  <details><summary>固定150只：查看缺价、退出与完整样本</summary>{endpointAvailable&&<p><a href="#st-endpoint-reasons">为什么完整段缺4只、最近9日缺3只？逐家公司看端点与退出阶段 →</a></p>}<p>三个缺口继续留在分母里：康佳缺共同端点；岭南停牌，尚未取得最终终止上市日期；萃华11月13日摘牌，不能借最后交易价冒充19日价格。萃华在本次窗口前已离开动态ST名单。</p><button type="button" className="regime-text-link" onClick={()=>setAll(v=>!v)}>{all?'只看缺价样本':'展开全部150只'}</button><table className="regime-table" aria-label="最新固定样本价格覆盖"><thead><tr><th>代码 / 历史简称</th><th>同窗收益</th><th>价格缺口</th></tr></thead><tbody>{rows.map(r=><tr key={r.symbol}><th>{r.symbol} {r.name}</th><td>{pct(r.return_pct)}</td><td>{r.gap??'共同端点可比'}</td></tr>)}</tbody></table>{d.events.filter(e=>e.symbol==='002717'||e.symbol==='002731').map(e=><p key={e.id}><a href={e.source.url} target="_blank" rel="noreferrer">{e.name} · {e.title} ↗</a>：{e.change}</p>)}</details>
  <details><summary>本轮来源与核验范围</summary><p>七家公司51条公告目录中，有目的选取11份公告48页。五只重点股票49个实际成交证券日，原价与前复权共98个价格点和另一渠道一致；两项指数20个点按官方两位小数一致，仍保留未取整精度差异。</p><p>{d.boundary}</p><p>本节没有更新市场页的ETF数据，也没有新增完整官方ST名单认证。新增公告不是11次独立经验验证。</p></details>
 </section>
}
