import {STEndpointSelectionAudit,type EndpointSelectionAudit} from './STEndpointSelectionAudit'
import {useState} from 'react'
type Endpoint={date:string;data_status:string;traded_qfq_close:number|null;reference_qfq_close:number|null;meaning:string}
type Row={symbol:string;name:string;return_pct:number|null;gap:string|null;anchor:Endpoint;endpoint:Endpoint;provider_st_at_end:boolean}
export type EndpointReasons={through:string;windows:{key:string;anchor:string;through:string;days:number;total:number;covered:number;missing:number;rows:Row[]}[];cases:{symbol:string;title:string;reading:string;sources:{source:{url:string;title:string;published_on:string;original_observed_at:string;reused:boolean};pages:number[]}[]}[];directory_review:{start:string;through:string;record_count:number;matched_final_titles:string[];scope:string};counts:{new_primary_documents:number;reused_primary_documents:number;reused_primary_pages:number;rechecked_rendered_pages:number;new_price_points:number};boundaries:string[];method_promotions:number}
const price=(n:number|null)=>n==null?'无当日成交端点':`${n.toFixed(2)}元（前复权）`
const pct=(n:number|null)=>n==null?'不计算':`${n>0?'+':''}${n.toFixed(2)}%`
export function STEndpointReasons({data:d,audit}:{data?:EndpointReasons|null;audit?:EndpointSelectionAudit|null}){
 const [key,setKey]=useState('full'),[symbol,setSymbol]=useState('000016')
 if(!d)return null
 const w=d.windows.find(w=>w.key===key)??d.windows[0],selected=w.rows.find(r=>r.symbol===symbol)??w.rows[0],caseReading=d.cases.find(c=>c.symbol===selected.symbol)!
 return <section id="st-endpoint-reasons" className="regime-topic-body" aria-label="固定样本缺价与退出解释">
  <p className="reading-kicker">固定7月3日150只 · 核到{d.through} · 保留停牌、退出和空值</p>
  <h3>缺价原因不同，换窗口也会换可比范围</h3>{audit&&<STEndpointSelectionAudit data={audit}/>}
  <p>完整93日有146只主源两端有成交、4只缺口；最近9日有147只主源两端有成交、3只缺口。多出来的龙元缺的是7月3日实际成交起点，近期窗口已有共同端点；这不表示名单多了一家公司。</p>
  <p>150只历史样本全部保留。146或147只是各窗口可以计算收益的子集；不能把空值填成0%，也不能把最后成交价、现金选择权或停牌参考价当作期末交易。</p>
  <p>表内价格为有成交证据的前复权收盘，用于统一收益口径，不是原始成交价；没有成交证据的端点保持空值。旧页面保留的原始价格不覆盖。</p>
  <label htmlFor="endpoint-window">想核哪段比较？</label><select id="endpoint-window" value={w.key} onChange={e=>setKey(e.target.value)}>{d.windows.map(w=><option key={w.key} value={w.key}>{w.key==='full'?'7月以来完整93日':'11月新增9日'} · {w.covered}/{w.total}可比、{w.missing}只缺口</option>)}</select>
  <div className="regime-scroll"><table className="regime-table"><caption>{w.anchor}收盘 → {w.through} · 以下四家都保留在150只原样本里</caption><thead><tr><th>选择公司</th><th>起点成交 / 前复权收盘</th><th>期末成交 / 前复权收盘</th><th>同窗收益</th></tr></thead><tbody>{w.rows.map(r=><tr key={r.symbol}><th><button className="regime-text-link" aria-pressed={r.symbol===selected.symbol} onClick={()=>setSymbol(r.symbol)}>{r.name}</button><small>{r.symbol}</small></th><td>{price(r.anchor.traded_qfq_close)}<small>{r.anchor.meaning}</small></td><td>{price(r.endpoint.traded_qfq_close)}<small>{r.endpoint.meaning}</small></td><td>{pct(r.return_pct)}</td></tr>)}</tbody></table></div>
  <h4>{selected.name}：{caseReading.title}</h4><p>{caseReading.reading}</p>
  <p>11月19日提供方动态ST名单：{selected.provider_st_at_end?'仍列在名单':'不在名单'}。这与交易是否发生、法律程序是否完成分别核，不能由其中一项代替另一项。</p>
  <details><summary>查看此公司的原件与价格缺口</summary><p>本窗口数据缺口：{selected.gap??'两端都有成交证据，可计算同窗价格变化。'}</p>{[selected.anchor,selected.endpoint].filter(e=>e.traded_qfq_close==null&&e.reference_qfq_close!=null).map(e=><p key={e.date}>{e.date}提供方有{e.reference_qfq_close!.toFixed(2)}元前复权参考值，但没有实际成交；该参考价不进入主收益计算。</p>)}{caseReading.sources.map(s=><article key={s.source.url}><p>披露{s.source.published_on} · 本轮复用原件，保留原采集时间。</p>{s.pages.map(n=><p key={n}><a href={s.source.url.replace(/#.*$/,'')+'#page='+n} target="_blank" rel="noreferrer">{s.source.title} · 第{n}页 ↗</a></p>)}</article>)}</details>
  <h4>岭南最终决定，为什么仍列为未核？</h4><p>公司原件支持停牌和收到事先告知；本次补查{d.directory_review.start}至{d.directory_review.through}完整返回的{d.directory_review.record_count}条目录，{d.directory_review.matched_final_titles.length?`发现${d.directory_review.matched_final_titles.length}个待核标题`:'标题中未定位明确最终决定或摘牌文件'}。这不能证明最终文件不存在，也不能把规则期限推成已摘牌。</p>
  <h4>原判断保留什么，下一步核什么？</h4><p>保留原收益空值和历史分母。康佳核现金选择权具体资格及账户结果，岭南核正式最终决定与摘牌原件，萃华后续股份登记另查；龙元的起点停牌不因后来复牌而被补成可交易日。新原件或有效成交记录出现时，先核对应日期，再更新解释。</p>
  <details><summary>本轮复用了什么，哪些没有新增？</summary><p>复用{d.counts.reused_primary_documents}份{d.counts.reused_primary_pages}页已核原件，重新查看{d.counts.rechecked_rendered_pages}个关键页；新增原件下载{d.counts.new_primary_documents}份、新增行情{d.counts.new_price_points}点。原行情、收益及旧研究未改写。</p>{d.boundaries.map(b=><p key={b}>{b}</p>)}<p>{d.directory_review.scope}</p></details>
 </section>
}
