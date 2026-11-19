import {useState} from 'react'
type Window={anchor:string;through:string|null;days:number|null;stock_pct:number|null;st_pct:number|null;market_pct:number|null}
type Source={announcement_id:string;title:string;url:string;published_on:string;reused:boolean}
type Financial={key:string;label:string;period:string;unit:string;values:Record<string,number>;yi_yuan:Record<string,number>;cash_derived:boolean;audited:boolean}
export type YigouSettlement={symbol:string;through:string;lead:string;specific_settlement_stage:string;financials:Financial[];monthly:Window[];full:Window;events:{source_id:string;published_on:string;windows:(Window&{requested_days:number;complete:boolean})[]}[];sources:Source[];catalog_count:number;scope_traps:{label:string;finding:string;source_id:string;pages:number[]}[];counts:{new_files:number;new_pages:number;reused_files:number;reused_pages:number;critical_pages_viewed:number;stock_daily_crosschecks:number;index_daily_crosschecks:number;new_quote_requests:number};boundaries:string[];method_promotions:number}
const pct=(v:number|null)=>v==null?'窗口未满':`${v>0?'+':''}${v.toFixed(2)}%`
const money=(v:number)=>`${v>0?'+':''}${v.toFixed(2)}`
export function STYigouSettlement({data:d}:{data?:YigouSettlement|null}){
 const [event,setEvent]=useState('1225532237')
 if(!d)return null
 const order=['half','quarter','nine'].map(key=>d.financials.find(r=>r.key===key)!)
 const selected=d.events.find(r=>r.source_id===event)??d.events[0]
 const links=(aid:string,pages:number[])=>{const s=d.sources.find(r=>r.announcement_id===aid)!;return <>{pages.map(n=><p key={n}><a href={s.url+'#page='+n} target="_blank" rel="noreferrer">{s.title} · 第{n}页 ↗</a></p>)}</>}
 return <section id="st-yigou-settlement" className="regime-reading-section" aria-label="易购和解、经营与现金复盘">
  <p className="reading-kicker">ST易购 · 002024 · 证据及行情截至{d.through}</p>
  <h3>利润为正，经营和现金也修复了吗？</h3><p>{d.lead}</p>
  <h4>先分开看利润、扣非与现金</h4>
  <p>单位：亿元。三列分别是半年、第三季度单季和前三季累计，不把累计数当成单季。两份报告均未经审计。</p>
  <div className="regime-scroll"><table className="regime-table" aria-label="易购利润扣非与现金对照"><thead><tr><th>看什么</th>{order.map(r=><th key={r.key}>{r.label}</th>)}</tr></thead><tbody>{[['net','归母净利润'],['core','扣非归母净利润'],['cash','经营现金流净额']].map(([key,label])=><tr key={key}><th>{label}</th>{order.map(r=><td key={r.key}>{money(r.yi_yuan[key])}</td>)}</tr>)}</tbody></table></div>
  <p>前三季度归母盈利约0.54亿元，扣非却亏损约35亿元。累计经营现金流约15.01亿元，但第三季度单季约净流出1.19亿元；“累计为正”不能替代最新单季的变化。</p>
  <details><summary>这些数字怎样核对？</summary><p>第三季度经营现金流由前三季累计减上半年累计推导；季度利润与扣非同时与三季报单季列核对。非经常性损益合计加扣非归母净利润等于归母净利润，但非经常性损益合计已经含税和少数股东影响，不能再把其中债务重组损益加一次。</p><table className="regime-table" aria-label="易购非经常性损益桥接"><thead><tr><th>亿元</th>{order.map(r=><th key={r.key}>{r.label}</th>)}</tr></thead><tbody>{[['nonrecurring','非经常性损益合计'],['debt','其中：债务重组损益']].map(([key,label])=><tr key={key}><th>{label}</th>{order.map(r=><td key={r.key}>{money(r.yi_yuan[key])}</td>)}</tr>)}</tbody></table><p>这都是公司汇总口径，不能全部归到6月那笔和解。半年报还披露“7月至目前”的初步统计，它属于期后更新，不倒填进上半年。</p>{links('1225532237',[6,7,55,63,148,153,154])}{links('1225638414',[1,2,12,13])}</details>
  <h4>6月那笔和解，究竟核到了哪一步？</h4><p>{d.specific_settlement_stage}。</p><p>股东会通过这一旧待办已经关闭；预计豁免金额、另一侧审批、正式签约、分期支付与实际收益确认仍要逐笔接上。后续财报出现收益，不自动补全这条履约链。</p>
  <details><summary>看审批原件与容易混淆的三件事</summary>{links('1225388521',[1,4])}{d.scope_traps.map(r=><article key={r.label}><h5>{r.label}</h5><p>{r.finding}</p>{links(r.source_id,r.pages)}</article>)}<p>本轮取得7月1日至11月19日完整返回的{d.catalog_count}条目录，并读两份财报的相关正文；没有定位完整履约链，不能当成后续文件不存在。</p></details>
  <h4>放回同期行情：不能只用“盈利”解释涨跌</h4><p>7月3日收盘至11月19日，易购{pct(d.full.stock_pct)}，主板ST参考{pct(d.full.st_pct)}，中证全指{pct(d.full.market_pct)}。利润、扣非、现金和价格方向不同，应分别解释。</p>
  <details><summary>逐月比较个股、ST与大盘</summary><table className="regime-table" aria-label="易购逐月同窗行情"><thead><tr><th>共同收盘窗口</th><th>易购</th><th>ST参考</th><th>中证全指</th></tr></thead><tbody>{d.monthly.map(r=><tr key={r.through}><th>{r.anchor} → {r.through}</th><td>{pct(r.stock_pct)}</td><td>{pct(r.st_pct)}</td><td>{pct(r.market_pct)}</td></tr>)}</tbody></table><p>11月只到19日；区间涨跌不等于该月公告贡献。</p></details>
  <details><summary>财报披露前后，同一窗口怎样变化？</summary><label>选择财报 <select value={selected.source_id} onChange={e=>setEvent(e.target.value)}>{d.events.map(r=><option key={r.source_id} value={r.source_id}>{r.published_on} · {r.source_id==='1225532237'?'半年报':'三季报'}</option>)}</select></label><p>以前一交易日收盘为起点；周末披露从下一交易日观察，最早公开时刻未核，不当可执行收益。</p><table className="regime-table" aria-label="易购财报披露观察窗口"><thead><tr><th>市场日数</th><th>共同日期</th><th>易购</th><th>ST</th><th>大盘</th></tr></thead><tbody>{selected.windows.map(r=><tr key={r.requested_days}><th>{r.requested_days}日</th><td>{r.anchor} → {r.through??'未满'}</td><td>{pct(r.stock_pct)}</td><td>{pct(r.st_pct)}</td><td>{pct(r.market_pct)}</td></tr>)}</tbody></table></details>
  <h4>原判断怎样更新，什么新证据会改变它？</h4><p>保留“公司股东会已通过、分期兑现仍需核”的判断；新增财报把“归母盈利”拆为扣非亏损、非经常性收益及现金变化。若取得同一和解的持有人会议、正式协议、逐期支付及确认依据，再更新对应阶段；若后续扣非与现金持续改善，再检验经营修复。</p>
  <details><summary>核验范围与尚未解决的问题</summary><p>新增{d.counts.new_files}份{d.counts.new_pages}页财报，复用{d.counts.reused_files}份{d.counts.reused_pages}页旧公告；实际核看{d.counts.critical_pages_viewed}关键页。既有报价响应复核94个股、188指数逐日点，新增报价请求为0；复用不计作新增独立来源。</p>{d.boundaries.map(t=><p key={t}>{t}</p>)}</details>
 </section>
}
