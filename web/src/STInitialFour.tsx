import {useState} from 'react'
type Source={url:string;title:string;published_on:string;document_dated_on:string;sha256:string}
type Comparison={anchor:string;through:string;days:number;stock_pct:number|null;market_pct:number|null;st_pct:number|null;gap:string|null}
type QuoteAudit={stock_endpoint_points:number;stock_return_windows:number;stock_max_float_tail:string;stock_absolute_tolerance:string;index_endpoint_points_at_official_precision:number;unrounded_index_differences:{index:string;date:string;provider:string;official:string}[];source_refs:{key:string;url:string;sha256:string;observed_at:string}[]}
export type InitialFour={quote_audit?:QuoteAudit;anchor:string;through:string;rows:{symbol:string;name:string;risk_group:string;known_at_anchor:string;watch:string;source:Source;pages:number[];supporting:{source:Source;pages:number[];note:string}[];comparisons:{early20:Comparison;full:Comparison}}[];inventory:{symbol:string;name:string;has_timely_reading_facts:boolean;new_this_round:boolean;latest_fact_on:string|null;fact_ids:string[]}[];counts:{before:number;after:number;remaining:number;members:number;new_companies:number;new_files:number;new_pages:number};selection_note:string;boundary:string;method_promotions:number;full_membership_certification_added:boolean}
const pct=(n:number|null)=>n==null?'缺价，保留空值':`${n>0?'+':''}${n.toFixed(2)}%`
export function STInitialFour({data:d}:{data?:InitialFour|null}){
 const [symbol,setSymbol]=useState('000056')
 const [period,setPeriod]=useState<'early20'|'full'>('full')
 const [scope,setScope]=useState('missing')
 if(!d)return null
 const selected=d.rows.find(r=>r.symbol===symbol)??d.rows[0]
 const window=d.rows[0].comparisons[period]
 const xilv=d.rows.find(r=>r.symbol==='000610')
 const inventory=d.inventory.filter(r=>scope==='all'||!r.has_timely_reading_facts)
 return <section className="regime-reading-section" aria-label="四家期初警示补证与同窗比较">
  <p className="reading-kicker">本批补齐期初事实 · {d.counts.before} → {d.counts.after}/{d.counts.members}家 · 仍缺{d.counts.remaining}家</p>
  <h4>相似的财务警示，后续涨跌仍然不同</h4>
  <p>皇庭、中迪、西旅都披露了负净资产的警示依据，但同时受到的约束仍有区别；晨鸣另有旧警示和已披露修复，不能一直停留在旧原因。把当时已知条件放在一起，再看同窗行情，才能避免用简称替代研究。</p>
  <label>期初四家比较窗口 <select value={period} onChange={e=>setPeriod(e.target.value as 'early20'|'full')}><option value="full">7月以来完整已覆盖窗口</option><option value="early20">规则后最初20个交易日</option></select></label>
  <p>{window.anchor}收盘 → {window.through} · {window.days}个交易日；同期中证全指{pct(window.market_pct)}，主板ST参考{pct(window.st_pct)}。</p>
  <div className="regime-scroll"><table className="regime-table" aria-label="期初四家风险与同窗表现"><thead><tr><th>固定样本中的A股</th><th>截至7月3日可见的约束</th><th>同窗股价变化</th></tr></thead><tbody>{d.rows.map(r=><tr key={r.symbol}><th>{r.name}<small>{r.symbol}</small></th><td>{r.risk_group}</td><td>{pct(r.comparisons[period].stock_pct)}</td></tr>)}</tbody></table></div>
  {xilv&&<p>西旅最初20日为{pct(xilv.comparisons.early20.stock_pct)}，完整窗口为{pct(xilv.comparisons.full.stock_pct)}。同一起点换一个终点，会改变“后来涨没涨”的答案；解释这段转变，还需继续核后续公告。</p>}
  <p className="reading-caption">{d.quote_audit?`四股${d.quote_audit.stock_endpoint_points}个前复权共同端点已与另一渠道核对；两指数${d.quote_audit.index_endpoint_points_at_official_precision}个端点按官方公布精度一致，未取整差异保留。`:'同窗股价变化使用既有提供方前复权端点；本批补公告正文，不新增这四股的跨渠道行情认证。'}</p>
  {d.quote_audit&&<details><summary>共同价格端点，跨渠道核到哪一步？</summary><p>核对7月3日、7月31日、11月19日三个收盘端点，覆盖四股的两个窗口。提供方数字有极小机器浮点尾差；指数原数与中证官方两位小数存在末位精度差，未覆盖原数。这不是全期每日报价的独立认证。</p><p>指数未取整差异共{d.quote_audit.unrounded_index_differences.length}个端点。</p>{d.quote_audit.source_refs.map(s=><p key={s.key}><a href={s.url} target="_blank" rel="noreferrer">{s.key.startsWith('sz')?d.rows.find(r=>r.symbol===s.key.slice(2))?.name:s.key==='000985'?'中证全指':'中证2000'} · {s.key.startsWith('sz')?'另一渠道前复权日线':'官方历史指数'} ↗</a></p>)}</details>}
  <p>这些比较检验“同一标签是否足够解释走势”，不把风险类别当成收益预测。尚未核齐这四家公司期间全部催化，不能由涨跌反推整改完成，或把差值当公告贡献。</p>
  <label>选择公司核对期初原件 <select value={symbol} onChange={e=>setSymbol(e.target.value)}>{d.rows.map(r=><option key={r.symbol} value={r.symbol}>{r.name}</option>)}</select></label>
  <h4>{selected.name}：当时已经知道什么？</h4><p>{selected.known_at_anchor}</p><p>继续核对：{selected.watch}</p>
  <details><summary>查看警示依据、修复披露与日期</summary><p>主依据披露{selected.source.published_on}，文件落款{selected.source.document_dated_on}。</p>{selected.pages.map(page=><p key={page}><a href={selected.source.url+'#page='+page} target="_blank" rel="noreferrer">{selected.source.title} · 第{page}页 ↗</a></p>)}{selected.supporting.map(s=><article key={s.source.sha256}><p>{s.note}</p><p>披露{s.source.published_on}，落款{s.source.document_dated_on}。</p>{s.pages.map(page=><p key={page}><a href={s.source.url+'#page='+page} target="_blank" rel="noreferrer">{s.source.title} · 第{page}页 ↗</a></p>)}</article>)}</details>
  <details><summary>覆盖如何更新，哪些仍缺？</summary><p>新增{d.counts.new_files}份{d.counts.new_pages}页，涉及4家公司。已有期初可知正文事实从42家增至46家；这不表示所有警示条件均已完整核清，也不新增完整官方历史名录认证。旧42家资料按原版本保留。</p><p>{d.selection_note}</p><label>期初事实覆盖名单 <select value={scope} onChange={e=>setScope(e.target.value)}><option value="missing">尚缺正文事实的104家</option><option value="all">完整150只</option></select></label><table className="regime-table" aria-label="更新后的期初事实覆盖名单"><thead><tr><th>代码与历史简称</th><th>已取得期初可知正文事实</th><th>本批新增</th></tr></thead><tbody>{inventory.map(r=><tr key={r.symbol}><th>{r.symbol} {r.name}</th><td>{r.has_timely_reading_facts?'有':'仍缺'}</td><td>{r.new_this_round?'是':'—'}</td></tr>)}</tbody></table></details>
  <p className="reading-caption">{d.boundary}</p>
 </section>
}
