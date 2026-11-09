import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import {STHukeDateProof} from './STHukeDateProof'
import {originalSourceTitle} from './officialSourceTitle'
import {STOfficialPDFAudit,OfficialCopyLink} from './STOfficialPDFAudit'
import {STBaoxinHoldingBridge} from './STBaoxinHoldingBridge'
import {STBaoxinAuctionLinks} from './STBaoxinAuctionLinks'
import {STDisclosureChains} from './STDisclosureChains'
import {STExperienceCaseAudit} from './STExperienceCaseAudit'
import {STRemovalEraComparison} from './STRemovalEraComparison'
import {STPreRuleMembership} from './STPreRuleMembership'
import {STDynamicReferenceAudit} from './STDynamicReferenceAudit'
import {STExitQuoteReplay} from './STExitQuoteReplay'
import {STRemainingBasis} from './STRemainingBasis'
import {STDividendBasis} from './STDividendBasis'
import {STFixedQuoteAudit} from './STFixedQuoteAudit'
import {useQuestionNavigation} from './stQuestionNavigation'
import {STShenwuExecution} from './STShenwuExecution'
import {STEarningsWarning} from './STEarningsWarning'
import {STStrongRemovalCases} from './STStrongRemovalCases'
import {STRemovalCohort} from './STRemovalCohort'
import {STRemovalFollowup} from './STRemovalFollowup'
import {STCompanyRiskCases} from './STCompanyRiskCases'
import {STIssuerCheck} from './STIssuerCheck'
import {STHaltStages} from './STHaltStages'
import {STStockPriceCrosscheck} from './STStockPriceCrosscheck'
import {useState} from 'react'
import type {ReactNode} from 'react'
import type {RegimeComparison,STRegimeData} from './stRegimeTypes'
const pct=(v:number|null|undefined)=>v==null?'待核':`${v>0?'+':''}${v.toFixed(2)}%`
const readableFact=(text:string)=>text.replace(/(-?\d+(?:\.\d+)?)元/g,(original,amount:string)=>{const n=Number(amount);return Math.abs(n)>=100000000?`约${(n/100000000).toFixed(2)}亿元`:Math.abs(n)>=10000?`约${(n/10000).toFixed(2)}万元`:original})
const phaseReading=(st:number,market:number)=>st>=0&&market>=0?`均上涨，ST${st>=market?'涨得更多':'涨得较少'}`:st<0&&market<0?`均下跌，ST${st>=market?'跌得较少':'跌得更多'}`:st>=0?'ST上涨，大盘下跌':'ST下跌，大盘上涨'
const topics=[['journey','这几个月发生了什么','先看过程'],['market','大盘影响有多明显','看同向与背离'],['events','公告到底改变了什么','看公司与阶段'],['lessons','下次怎样看得更准','看条件与反例']] as const
export function STRegimeThemes({data,comparison,chart,onEvidence}:{data:STRegimeData;comparison:RegimeComparison;chart:ReactNode;onEvidence:(view:string,targetId?:string)=>void}){
 const {topic,select:setTopic,questions,companyOverride}=useQuestionNavigation(data)
 const [requestedSymbol,setSymbol]=useState('603398')
 const symbol=companyOverride??requestedSymbol
 const [window,setWindow]=useState('5')
 const [showAll,setShowAll]=useState(false)
 const themes=data.themes,ann=themes?.announcement_reading??themes?.announcements
 const all=data.comparisons.find(c=>c.key==='all')??comparison
 const after=all.after,fixed=all.fixed_after
 const companies=Array.from(new Map((ann?.verified_events??[]).map(e=>[e.symbol,e.name])).entries()).sort((a,b)=>a[0].localeCompare(b[0]))
 const selected=companies.some(([s])=>s===symbol)?symbol:companies[0]?.[0]
 const events=(ann?.verified_events??[]).filter(e=>e.symbol===selected)
 const condition=after.conditions.find(c=>c.key==='down')
 return <div className="regime-topics">
  <p className="regime-topic-intro">想弄清哪件事？选一个问题，先看答案，再核对过程和证据。</p>
  <nav className="regime-topic-nav" aria-label="复盘问题">{topics.map(([key,title,sub],i)=><button type="button" key={key} aria-pressed={topic===key} onClick={()=>setTopic(key)}><small>0{i+1} · {sub}</small><span>{title}</span></button>)}</nav>
  {questions.length>0&&<div className="regime-question-directory">
   <label htmlFor="st-case-question">按具体问题查阅</label>
   <select id="st-case-question" value={questions.some(q=>q.key===topic)?topic:''} onChange={e=>setTopic(e.target.value)}>
    <option value="" disabled>选择公司或比较题 · {questions.length}个专题</option>
    {questions.map(q=><option key={q.key} value={q.key}>{q.title}</option>)}
   </select>
   <p>每次只展开所选问题。切换总览或案例时，资料截止与证据保持不变。</p>
   {themes?.pre_rule_membership?<button className="regime-text-link" onClick={()=>setTopic('market')}>本轮新核：制度前移出的48只，究竟去了哪里？ →</button>:themes?.dynamic_reference_audit?<button className="regime-text-link" onClick={()=>setTopic('market')}>本轮新核：动态ST参考线，按哪些股票核过？ →</button>:themes?.exit_quote_replay?<button className="regime-text-link" onClick={()=>setTopic('quoteaudit')}>本轮新核：退出样本已重放，哪些比较发生变化？ →</button>:themes?.remaining_basis?<button className="regime-text-link" onClick={()=>setTopic('dividends')}>本轮新核：剩余8只差异，分别是什么原因？ →</button>:themes?.dividend_basis?<button className="regime-text-link" onClick={()=>setTopic('dividends')}>本轮新核：同一天的涨幅，为什么有三种读数？ →</button>:themes?.fixed_quote_audit?<button className="regime-text-link" onClick={()=>setTopic('quoteaudit')}>本轮新核：固定150只的行情，核对到了哪一步？ →</button>:themes?.earnings_warning&&<button className="regime-text-link" onClick={()=>setTopic('earnings')}>本轮新核：盈利和现金都转好，为什么还在ST？ →</button>}
  </div>}
  {themes?.baoxin_auction_links&&<button className="regime-text-link" onClick={()=>{setSymbol('002514');setShowAll(false);setTopic('baoxin')}}>宝馨：过户对应哪笔竞拍？核分笔股份 →</button>}
  {themes?.disclosure_chains&&<button className="regime-text-link" onClick={()=>setTopic('events')}>同日两份公告，是两次新进展吗？沿事项链核对 →</button>}
  {themes?.experience_case_audit&&<button className="regime-text-link" onClick={()=>setTopic('lessons')}>本轮经验检验：首日上涨，后来也涨吗？ →</button>}
  {themes?.price_band_audit&&<button className="regime-text-link" onClick={()=>onEvidence('规则前后','st-price-band-audit')}>涨过5%，就突破旧涨停了吗？看具体例子 →</button>}
  {themes?.removal_era_comparison&&<button className="regime-text-link" onClick={()=>setTopic('cohort')}>本轮比较：摘帽以后，7月前后有什么不同？ →</button>}
  <p className="regime-topic-date">观察期 {after.start} — {data.through} · {after.days} 个交易日 · 末月只到{data.through}；不是整月</p>
  {topic==='journey'&&<div id="st-question-journey" className="regime-topic-body">
   <p className="reading-kicker">先看答案</p><h3>{(after.reference_change_pct??0)<0?(after.reference_change_pct??0)>(after.market_change_pct??0)?'整体跌得比大盘少，个股还要分别看':'整体仍在下跌，个股还要分别看':'整体参考回升，个股还要分别看'}</h3>
   <p>完整后窗ST等权参考 {pct(after.reference_change_pct)}，中证全指 {pct(after.market_change_pct)}。固定7月3日的{fixed.total}只股票中，{fixed.covered}只两端有成交证据，{fixed.positive_pct==null?'上涨覆盖面待核':`其中约${fixed.positive_pct.toFixed(0)}%上涨`}，中位数 {pct(fixed.median_pct)}；另{fixed.missing}只缺口保留。“相对强”与“多数赚钱”是两件事。</p>
   {themes?.sample_integrity&&<p>先前两处缺价：康佳A缺退出后的期末交易价，萃华缺停牌中的比较起点。另有参考价却无成交的端点，已从主分布分开，股票都保留。<button className="regime-text-link" onClick={()=>onEvidence('整批个股','st-sample-integrity')}>查看两处缺口的公告依据 →</button></p>}
   {fixed.reference_summary&&<p>原参考价口径有{fixed.reference_summary.covered}只可算；核成交状态后，主分布为{fixed.covered}只。<button className="regime-text-link" onClick={()=>onEvidence('整批个股','st-endpoint-audit')}>查看端点口径修正与旧数值 →</button></p>}{chart}
   <h4>过程拆开看，结论才不容易被起止点带偏</h4>
   {themes?.months?<div className="regime-scroll" role="region" aria-label="分月行情过程" tabIndex={0}><table className="regime-table"><thead><tr><th>阶段</th><th>ST参考</th><th>大盘</th><th>小盘风格</th><th>怎样理解</th><th>覆盖</th></tr></thead><tbody>{themes.months.map(m=><tr key={m.month}><th>{m.month}<small>{m.start} — {m.through}</small></th><td>{pct(m.st_pct)}</td><td>{pct(m.market_pct)}</td><td>{pct(m.small_pct)}</td><td>{phaseReading(m.st_pct,m.market_pct)}</td><td>{m.days}日</td></tr>)}</tbody></table></div>:<p>本版没有独立分月资料，请展开核对已有窗口。</p>}
   <p className="reading-caption">各月按实际覆盖交易日连乘，7月从6日开始，末月只到{data.through}。各月涨跌幅不能相加；小盘风格使用中证2000。</p>
   {themes?.member_entries&&<><h4>新进来的公司，为什么被ST？</h4><p>6家新增的直接原因分成几类：正式重整受理、主要银行账户冻结、控股股东资金占用、财报监管事项。相同的ST标签，不替代对主体、程序和整改条件的判断。</p><button className="regime-text-link" onClick={()=>onEvidence('整批个股','st-member-entries')}>查看新增原因与共同日期的行情对照 →</button></>}
   {themes?.initial_status_coverage&&<><h4>同样是上涨异动，后面的风险和走势一样吗？</h4><p>六份7月3日原件把签约、摘帽申请、财务约束和股东变卖分开；同窗价格随后明显分化。</p><button className="regime-text-link" onClick={()=>setTopic('initialstatus')}>看期初风险状态与六家后续走势 →</button></>}
   {themes?.member_transitions&&<><h4>名单变小了，里面发生了什么？</h4><p>7月3日有{data.universe.anchor_members}只，期末有{data.universe.endpoint_members}只；期间{data.universe.exits.length}只移出、{data.universe.entrants.length}只新增。已核的移出路径包括撤销风险警示、主动摘牌和退市整理，不能把人数净减少当作同一种结果。</p><button className="regime-text-link" onClick={()=>onEvidence('整批个股','st-member-transitions')}>查看每家为什么离开ST名单 →</button></>}
   {themes?.label_changes&&<>{data.themes?.membership_audit&&<><h4>名单本身，已经独立核实了吗？</h4><p>{data.themes.membership_audit.answer}</p><button className="regime-inline-action" onClick={()=>onEvidence('整批个股','st-membership-audit')}>查看名单核验范围与缺口 →</button></>}<h4>简称变了，风险一定变了吗？</h4><p>三处星号变化各有具体警示含义，另外两家是XD除息标记；变化当天都没有因此离开ST池。除息还会使原始收盘变化与参考价涨跌不同，先核日期和口径。</p><button className="regime-text-link" onClick={()=>onEvidence('整批个股','st-label-changes')}>查看星号、XD与除息价格口径 →</button></>}<h4>再问：与规则改变之前有什么区别？</h4><p>前后各40日：ST参考从 {pct(comparison.key==='40'?comparison.before.reference_change_pct:data.comparisons.find(c=>c.key==='40')?.before.reference_change_pct)} 到 {pct(data.comparisons.find(c=>c.key==='40')?.after.reference_change_pct)}。完整后窗更长，回答的是后来走了多远；等长窗口才用于前后描述比较。只有一次规则事件，仍无法隔离市场、公告和预期交易的影响。</p>
   <button className="regime-text-link" onClick={()=>onEvidence('规则前后')}>核对等长20/40日、波动与旧5%边界 →</button>
  </div>}
  {topic==='market'&&<div id="st-question-market" className="regime-topic-body"><STPreRuleMembership data={themes?.pre_rule_membership} audit={themes?.official_pdf_audit} hukeProof={themes?.huke_date_proof} onHuke={()=>{setSymbol('600608');setShowAll(false);setTopic('huke')}}/><STDynamicReferenceAudit data={themes?.dynamic_reference_audit} preRuleChecked={Boolean(themes?.pre_rule_membership)}/><p className="reading-kicker">先看答案</p><h3>市场环境不能略过，影响份额仍不能分摊</h3><p>规则后大盘下跌的 {condition?.days} 天，ST参考日均 {pct(condition?.st_mean_pct)}；上涨日的日均表现为 {pct(after.conditions.find(c=>c.key==='up')?.st_mean_pct)}。同向与背离都要保留，不能把某天个股涨跌直接归给公司公告。</p>{themes?.index_crosscheck&&<><h4>大盘数据本身，有没有核错？</h4><p>两项指数已接入第二报价渠道，展开可核对窗口涨跌、ST相对强弱和市场日期分类是否改变。仍保留{themes.index_crosscheck.precision_difference_count}个精度差异点，原行情没有被覆盖。</p><button className="regime-text-link" onClick={()=>onEvidence('大盘联动','st-index-crosscheck')}>查看两项指数的渠道核对与差异 →</button></>}<h4>先挑大盘波动最大的日子，核对ST是否一起动</h4><p>下表按大盘单日涨跌绝对值挑选前8日，再按时间排列。它便于发现市场冲击，不能代替全部交易日的统计。</p><div className="regime-scroll" role="region" aria-label="大盘波动较大交易日" tabIndex={0}><table className="regime-table"><thead><tr><th>日期</th><th>大盘</th><th>ST参考</th><th>当日ST上涨占比</th></tr></thead><tbody>{themes?.market_days.map(d=><tr key={d.date}><th>{d.date}</th><td>{pct(d.market_pct)}</td><td>{pct(d.return_pct)}</td><td>{pct(d.positive_pct)}</td></tr>)}</tbody></table></div><h4>看公告时，用同一窗口作对照</h4><p>先比较个股、主板ST参考与大盘是否同向，再问该公告有没有新增法律、财务或履约事实。相对大盘的差值是观察线索，不能直接解释成公告贡献。</p><button className="regime-text-link" onClick={()=>onEvidence('大盘联动')}>核对全部交易日、相关性与市场涨跌环境 →</button></div>}
  {topic==='events'&&<div id="st-question-events" className="regime-topic-body">{symbol==='600608'&&<STHukeDateProof data={themes?.huke_date_proof}/>}{symbol==='002514'&&themes?.baoxin_auction_links?themes.baoxin_holding_bridge?<><STBaoxinHoldingBridge data={themes.baoxin_holding_bridge} earlySources={themes.announcement_reading?.supplement?.sources} onOtherChains={()=>{setSymbol('603398');setShowAll(false);setTopic('events')}}/><details><summary>追溯上轮配对记录（不含本轮补证，非最新状态）</summary><STBaoxinAuctionLinks data={themes.baoxin_auction_links} historical/></details></>:<STBaoxinAuctionLinks data={themes.baoxin_auction_links} onOtherChains={()=>{setSymbol('603398');setShowAll(false);setTopic('events')}}/>:symbol==='600608'&&themes?.huke_date_proof?null:<STDisclosureChains data={themes?.disclosure_chains}/>}<p className="reading-kicker">先看问题</p><h3>公告发了以后，事情走到了哪一步？</h3><p>同一个“有进展”，可能只是签约，也可能已经付款或完成登记。把阶段串起来，再看随后个股与市场的同期变化，才能分清事实推进与价格表现。</p>
   {ann?<><p className="regime-topic-coverage">目录：{ann.companies}家公司、{ann.catalog_rows.toLocaleString()}条披露。正文选样：{ann.verified_companies}家公司、{ann.verified_documents}份已核文件、{ann.deduplicated_event_count!=null?`${ann.deduplicated_event_count}个${ann.coverage_note?'阅读事项':'去重事项'}（${ann.raw_fact_records}条事实记录）`:`${ann.verified_events.length}条已核记录`}。{ann.coverage_note??(ann.body_reads_this_refresh>0?`包括历史已核材料与本轮新核${ann.body_reads_this_refresh}份来源文件，未读完全部公告。`:'正文来自此前已核材料，本轮没有重新逐份读完全部公告。')}</p><STOfficialPDFAudit data={themes?.official_pdf_audit}/><div className="regime-stock-controls"><label>选择公司<select aria-label="公告复盘公司" value={selected??''} onChange={e=>{setSymbol(e.target.value);setShowAll(false);if(companyOverride)setTopic('events')}}>{companies.map(([s,n])=><option key={s} value={s}>{n} · {s}</option>)}</select></label><label>随后观察窗口<select aria-label="公告后观察窗口" value={window} onChange={e=>setWindow(e.target.value)}><option value="1">1个交易日</option><option value="5">5个交易日</option><option value="20">20个交易日</option></select></label></div><p className="reading-caption">从披露日收盘（非交易日取之前最近收盘）起算，随后完整交易日比较；没有精确发布时间，不把这当作最早市场反应。公告日内变化不计入。停牌、缺价与不足窗口保留待核。</p>
   <p className="reading-caption">{showAll?`完整展示本公司${events.length}条已核事件，按时间排列。`:`先看最近${Math.min(5,events.length)}条；早期事件可展开。`}</p><ol className="regime-event-list">{(showAll?events:events.slice(-5)).map(e=>{const w=e.observation.windows[window];return <li key={e.event_key??`${e.symbol}-${e.id}-${e.source.sha256}-${e.published_on}-${e.source.page}`}><p className="reading-kicker">{e.published_on}</p><h4>{e.title}</h4>{(e.source_record_count??1)>1&&<p className="reading-caption">同一事项保留{e.source_records?.length??1}个视角、{e.source_record_count}条原记录，行情窗口只观察一次，不作多次独立验证。</p>}{e.scheduled_for&&<p className="reading-caption">公告安排生效：{e.scheduled_for}；后续行情仍按披露日窗口观察。</p>}<p>{readableFact(e.change)}</p>{e.date_uncertainty&&<p className="regime-date-conflict"><strong>日期待核：</strong>{e.date_uncertainty}{e.alternate_observation&&<>按另一日期从{e.alternate_observation.anchor}收盘起，至{e.alternate_observation.windows[window].through??'窗口未满'}：个股{pct(e.alternate_observation.windows[window].stock_pct)}、大盘{pct(e.alternate_observation.windows[window].market_pct)}、ST参考{pct(e.alternate_observation.windows[window].st_pct)}。</>}</p>}<p>{e.interpretation}</p>{(e.same_company_day_facts??0)>1&&<p className="reading-caption">本公司同日{e.same_company_day_facts}项事实共享一次日期行情观察，不作多次独立验证。</p>}{e.background_only?<p className="reading-caption">前置背景，早于本轮行情覆盖，不计算公告后窗口。</p>:<><div className="regime-event-returns"><span>个股 <b>{pct(w.stock_pct)}</b></span><span>大盘 <b>{pct(w.market_pct)}</b></span><span>ST参考 <b>{pct(w.st_pct)}</b></span></div><p className="reading-caption">{e.observation.anchor} → {w.through??'后续窗口未满'}{w.gap?` · ${w.gap}`:''}；三者同窗，价格不证明公告因果。</p></>}<details><summary>查看依据与下一步核对</summary><p>{e.evidence_detail}</p><p>事实原数：{e.change}</p><p>继续核对：{e.watch}</p>{e.source_records?.length?e.source_records.map((r,n)=><div key={`${r.source.sha256}-${n}`}><p>{r.title}：{readableFact(r.change)}</p>{r.interpretation&&<p>{r.interpretation}</p>}<a href={r.source.url} target="_blank" rel="noreferrer">{originalSourceTitle(r.source.title,themes?.official_pdf_audit,r.source.sha256)} · 第{r.source.page}页 ↗</a><OfficialCopyLink audit={themes?.official_pdf_audit} sha256={r.source.sha256} page={r.source.page}/></div>):<><a href={e.source.url} target="_blank" rel="noreferrer">{originalSourceTitle(e.source.title,themes?.official_pdf_audit,e.source.sha256)} · 第{e.source.page}页 ↗</a><OfficialCopyLink audit={themes?.official_pdf_audit} sha256={e.source.sha256} page={e.source.page}/></>}{e.supporting_sources?.filter(s=>s.sha256!==e.source.sha256||s.page!==e.source.page).map(s=><p key={`${s.sha256}-${s.page}`}><a href={s.url} target="_blank" rel="noreferrer">补充依据：{originalSourceTitle(s.title,themes?.official_pdf_audit,s.sha256)} · 第{s.page}页 ↗</a></p>)}<p className="reading-caption">原件标识 {e.source.sha256.slice(0,12)}；公司主体范围 {e.entity_scope}。</p></details></li>})}</ol>{events.length>5&&<button className="regime-text-link" onClick={()=>setShowAll(v=>!v)}>{showAll?'收起早期事件':`展开本公司完整${events.length}条事件链 →`}</button>}<p className="reading-caption">{ann.boundary}</p></>:<p>本版尚未绑定公告正文选样；不以标题代替事实。</p>}
  </div>}
  {topic==='lessons'&&<div id="st-question-lessons" className="regime-topic-body"><STExperienceCaseAudit data={themes?.experience_case_audit}/><p className="reading-kicker">把逻辑留给下次</p><h3>先查变化，再看相对表现，最后保留反例</h3><div className="regime-lessons">
   <section><h4>① 先确定比较对象</h4><p>看整批行情，用每天当时在场的ST；看原来那批股票，用7月3日固定150只。两者回答不同问题，退市、摘帽与缺价都要留在记录里。</p><p><strong>何时重查：</strong>样本名单变化、停牌或端点缺失时，先检查分母和覆盖，再解释涨跌。</p><button className="regime-text-link" onClick={()=>onEvidence('整批个股')}>查看150只完整名单 →</button></section>
   <section><h4>② “有进展”要落实到履约</h4><p>宝馨竞得、异议重拍、再次竞得和过户是一条有回退的链；沐邦催收、诉讼受理与到账也需要分别核实。一个阶段不能提前代表最终完成。</p><p><strong>可能改变判断的证据：</strong>付款凭据、登记结果、法院裁定或正式终止；事实推进后仍要检查价格是否已经反映预期。</p><button className="regime-text-link" onClick={()=>setTopic('events')}>沿公告链核对 →</button></section>
   {themes?.member_entries&&<section><h4>先问实施原因，再核整改的时钟</h4><p>中基的直接触发是公司正式重整受理；富煌虽处预重整，直接触发的是主要账户冻结。三家财报监管事项中，事先告知书与正式处罚决定书不同，不能从ST生效日就开始确定的摘帽倒计时。</p><p>中基原件也披露投资款已按协议足额进入临时管理人账户。保留已缴事实，同时把账户主体、法院计划批准与最终执行分开。</p><button className="regime-text-link" onClick={()=>onEvidence('整批个股','st-member-entries')}>按原因与主体核原件 →</button></section>}
   {themes?.member_transitions&&<section><h4>状态更新先核生效日，再看还留哪些风险</h4><p>本轮12次撤销风险警示都发生在7月6日新规之后；多份原件说明摘帽后日涨跌幅仍为10%。不能把这批摘帽一概解释为放宽了价格限制，也不能把对应警示解除等同于主营扭亏或诉讼结束。</p><button className="regime-text-link" onClick={()=>onEvidence('整批个股','st-member-transitions')}>按公司核生效日与剩余风险 →</button></section>}
   {themes?.sample_integrity&&<section><h4>③ 缺价先查位置，再查状态</h4><p>缺起点、缺终点、停牌与摘牌会产生不同问题。萃华在期末仍有交易，不能因缺起点就写成已经退市；康佳A有现金选择权安排，也不能由摘牌直接推断所有人损失100%。</p><p><strong>何时暂停计算：</strong>没有同窗端点，或未核清具体持有人的权利和交收时，保留缺口，不借用更早价格拼接收益。</p><button className="regime-text-link" onClick={()=>onEvidence('整批个股','st-sample-integrity')}>核对两种缺口 →</button></section>}<section><h4>④ 市场与公司证据一起看</h4><p>同样的公告，处于普跌和普涨环境时，个股绝对涨跌容易给出不同印象。固定同一窗口比较个股、ST与大盘，保留“事实变好但价格下跌”与“风险仍在但价格上涨”的反例。</p><p><strong>仍不能回答：</strong>没有可比对照与精确时点，不能估计公告或规则各造成多少涨跌，也不能据此预测下次收益。</p></section>
  </div><p className="reading-caption">这些是本轮复盘的核对原则。一次制度变化、重叠窗口和同一公司多条公告不算独立实证，未自动晋级为经验证的交易方法。</p></div>}
  <div className="regime-selected-case">
   {topic==='dividends'&&(themes?.remaining_basis?<div id="st-dividend-basis"><STRemainingBasis data={themes.remaining_basis} explained={themes.fixed_quote_audit?.qfq_basis_explained_companies} exitReplayed={Boolean(themes.exit_quote_replay)}/><details><summary>回看章鼓、八菱：三个涨幅的具体例子</summary><STDividendBasis data={themes.dividend_basis} anchorId="st-dividend-basis-original"/></details></div>:<STDividendBasis data={themes?.dividend_basis}/>)}
   {topic==='quoteaudit'&&<div id="st-fixed-quote-audit"><STExitQuoteReplay data={themes?.exit_quote_replay}/><STFixedQuoteAudit data={themes?.fixed_quote_audit} anchorId="st-fixed-quote-audit-detail" dynamicPriceChecked={Boolean(themes?.dynamic_reference_audit)}/></div>}
   {topic==='prices'&&<div id="st-stock-price-check"><STStockPriceCrosscheck data={themes?.stock_price_crosscheck} onCompany={s=>{setSymbol(s);setShowAll(false);setTopic('events')}}/></div>}
   {topic==='earnings'&&<STEarningsWarning data={themes?.earnings_warning}/>}
   {topic==='cohort'&&<div id="st-removal-cohort"><STRemovalEraComparison data={themes?.removal_era_comparison} audit={themes?.official_pdf_audit}/>{themes?.removal_era_comparison?<details><summary>回看原12只摘帽股的停牌前起算比较</summary><STRemovalCohort data={themes?.removal_cohort}/></details>:<STRemovalCohort data={themes?.removal_cohort}/>}</div>}
   {topic==='strong'&&<STStrongRemovalCases data={themes?.strong_removal_cases}/>}
   {topic==='execution'&&<STShenwuExecution data={themes?.shenwu_execution}/>}
   {topic==='risk'&&<div id="st-company-risk-cases"><STCompanyRiskCases data={themes?.company_risk_cases} priceCheck={themes?.case_price_crosscheck}/></div>}
   {topic==='followup'&&<div id="st-removal-followup"><STRemovalFollowup data={themes?.removal_followup} comparison={themes?.company_risk_cases?.comparison}/></div>}
   {topic==='halts'&&<div id="st-halt-stages"><STHaltStages data={themes?.halt_stages} priceCheck={themes?.halt_price_crosscheck} onCompany={s=>{setSymbol(s);setShowAll(false);setTopic('events')}}/></div>}
   {topic==='initialstatus'&&<STInitialStatusCoverage data={themes?.initial_status_coverage} update={themes?.warning_basis_followup} ruihe={themes?.ruihe_process} three={themes?.initial_three_followup} quoteproof={themes?.initial_three_quoteproof} debt={themes?.zhongyan_debt_followup} day={themes?.initial_day_corroboration} origin={themes?.initial_warning_origin}/> }
   {topic==='issuer'&&<div id="st-issuer-checks">{themes?.membership_audit?.issuer_checks?.map(c=><STIssuerCheck key={c.symbol} check={c}/>)}</div>}
  </div>
  {questions.some(q=>q.key===topic)&&<p className="regime-question-return"><button className="regime-text-link" onClick={()=>setTopic('journey')}>返回整批行情总览 →</button><a href={'#'+questions.find(q=>q.key===topic)!.anchor}>此问题的固定链接</a></p>}
 </div>
}
