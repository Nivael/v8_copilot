import {useState} from 'react'
type Window={anchor:string;through:string|null;days:number|null;stock_pct:number|null;st_pct:number|null;market_pct:number|null;small_pct:number|null}
type Source={announcement_id:string;url:string;title:string;published_on:string;document_dated_on:string;pages_to_read:number[];sha256:string}
export type XilvTimeline={anchor:string;through:string;monthly:(Window&{title:string;reading:string})[];full:Window;path:{date:string;stock_close:number;stock_pct:number;st_pct:number;market_pct:number;small_pct:number}[];events:{key:string;published_on:string;title:string;reading:string;sources:Source[];windows:(Window&{requested_days:number;available_days:number;complete:boolean})[]}[];first_recovery_after_july:{date:string;stock_close:number};hindsight_extrema:{highest_close:{date:string;stock_close:number};lowest_close:{date:string;stock_close:number}};counts:{pdf_files:number;pdf_pages:number;catalog_rows:number;event_groups:number;complete_windows:number;incomplete_windows:number};crosscheck:{stock_daily_points:number;official_index_daily_points:number;unrounded_index_differences:{index:string;date:string;provider:string;official:string}[];sources:{key:string;url:string}[]};boundaries:string[];method_promotions:number;tracked_list_changed:boolean}
const pct=(n:number|null)=>n==null?'未满窗口':`${n>0?'+':''}${n.toFixed(2)}%`
const short=(s:string)=>s.slice(5).replace('-','/')
export function STXilvTimeline({data:d}:{data?:XilvTimeline|null}){
 const [phase,setPhase]=useState(0)
 const [event,setEvent]=useState('pre')
 if(!d)return null
 const selected=d.events.find(e=>e.key===event)??d.events[0]
 const month=d.monthly[phase]??d.monthly[0]
 const series=[{key:'stock_pct',label:'西旅',color:'#9c432e'},{key:'st_pct',label:'主板ST参考',color:'#416e58'},{key:'market_pct',label:'中证全指',color:'#345b83'}] as const
 const values=d.path.flatMap(r=>series.map(s=>r[s.key]));const low=Math.floor(Math.min(0,...values)/10)*10,high=Math.ceil(Math.max(0,...values)/10)*10
 const x=(i:number)=>54+i/(d.path.length-1)*620,y=(v:number)=>218-(v-low)/(high-low)*190
 return <section id="st-xilv-timeline" className="regime-topic-body" aria-label="西旅7月至11月过程复盘">
  <p className="reading-kicker">西旅 000610 · {d.anchor} — {d.through} · 后续事实不回填期初判断</p>
  <h3>先跌、修复、冲高、回撤、再反弹</h3>
  <p>完整93日西旅 {pct(d.full.stock_pct)}，但过程有五段。8月与ST、大盘共同修复，9月和11月则与市场背离；预重整、签约和借款是真实进展，尚不能据此证明重整完成或风险解除。</p>
  <figure style={{margin:'24px 0'}}>
   <svg viewBox="0 0 700 252" role="img" aria-label="7月3日收盘为零的累计收益：西旅、主板ST参考、中证全指" style={{width:'100%',maxHeight:350}}>
    <rect x={x(d.path.findIndex(r=>r.date===month.anchor))} y="18" width={x(d.path.findIndex(r=>r.date===month.through))-x(d.path.findIndex(r=>r.date===month.anchor))} height="208" fill="#ede9dd" opacity="0.55"/>
    {[low,0,high].map(v=><g key={v}><line x1="54" x2="674" y1={y(v)} y2={y(v)} stroke="#d7d2c9" strokeDasharray={v===0?undefined:'3 5'}/><text x="46" y={y(v)+4} textAnchor="end" fontSize="12" fill="currentColor">{v}%</text></g>)}
    {series.map(s=><polyline key={s.key} fill="none" stroke={s.color} strokeWidth="2.5" points={d.path.map((r,i)=>`${x(i)},${y(r[s.key])}`).join(' ')}/>)}
    {[d.anchor,...d.monthly.map(r=>r.through!)].map(day=>{const i=d.path.findIndex(r=>r.date===day);return <text key={day} x={x(i)} y="244" textAnchor={i===0?'start':i===d.path.length-1?'end':'middle'} fontSize="12" fill="currentColor">{short(day)}</text>})}
   </svg>
   <figcaption>{series.map(s=><span key={s.key} style={{color:s.color,marginRight:22}}>● {s.label}</span>)}累计收益以7月3日收盘为零；浅色区间为所选月份。ST按每日动态主板样本等权复合。</figcaption>
  </figure>
  <h4>先分清：哪些月份一起动，哪些月份背离？</h4>
  <div className="regime-scroll"><table className="regime-table"><caption>按交易日历月末切分 · 各段起点至终点收盘 · 11月不满整月</caption><thead><tr><th>起止收盘</th><th>交易日</th><th>西旅</th><th>ST参考</th><th>中证全指</th><th>中证2000</th></tr></thead><tbody>{d.monthly.map((r,i)=><tr key={r.anchor}><td><button className="regime-text-link" aria-pressed={phase===i} onClick={()=>setPhase(i)}>{short(r.anchor)}—{short(r.through!)}</button></td><td>{r.days}</td><td>{pct(r.stock_pct)}</td><td>{pct(r.st_pct)}</td><td>{pct(r.market_pct)}</td><td>{pct(r.small_pct)}</td></tr>)}</tbody></table></div>
  <p><strong>{month.title}：</strong>{month.reading}</p>
  <p>8月共同回升、10月共同下跌，市场背景不能省略；9月及11月方向相反，仅用大盘方向解释也不充分。相对收益不能直接分摊为公告贡献。</p>
  <h4>公告究竟把哪件事向前推进了？</h4>
  <label htmlFor="xilv-event">选择一个进展或反例</label>{' '}
  <select id="xilv-event" value={selected.key} onChange={e=>setEvent(e.target.value)}>{d.events.map(e=><option key={e.key} value={e.key}>{e.published_on} · {e.title}</option>)}</select>
  <h4>{selected.title}</h4><p>{selected.reading}</p>
  <div className="regime-scroll"><table className="regime-table"><caption>以披露前一交易日 {selected.windows[0].anchor} 收盘为锚 · 披露日 {selected.published_on}</caption><thead><tr><th>观察窗口</th><th>到哪天</th><th>西旅</th><th>ST参考</th><th>中证全指</th></tr></thead><tbody>{selected.windows.map(w=><tr key={w.requested_days}><td>后{w.requested_days}个交易日</td><td>{w.complete?w.through:`截至${d.through}仅${w.available_days}日`}</td><td>{pct(w.stock_pct)}</td><td>{pct(w.st_pct)}</td><td>{pct(w.market_pct)}</td></tr>)}</tbody></table></div>
  <p>未核准确发布时刻；这些是披露日附近的价格观察，不能当看到公告后可执行的收益。窗口可能重叠。</p>
  <details><summary>展开本事项原件、披露日与署期</summary>{selected.sources.map(s=><p key={s.announcement_id}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> · 披露{s.published_on} · 原件署期{s.document_dated_on} · 重点第{s.pages_to_read.join('、')}页</p>)}</details>
  <h4>两个时间反例：后来的进展解释不了全部上涨</h4>
  <p>{d.first_recovery_after_july.date}收盘{d.first_recovery_after_july.stock_close.toFixed(2)}元，已回到7月3日6.06元之上，早于9月预重整披露。区间最高收盘{d.hindsight_extrema.highest_close.date}为{d.hindsight_extrema.highest_close.stock_close.toFixed(2)}元，早于9月18日签约；9月22日披露当日反而下跌约9.98%。</p>
  <p>最高收盘和首次恢复日期来自事后完整路径，只用于复盘，不能倒填为当时可预测的拐点。</p>
  <h4>原判断怎样更新，下一步看什么？</h4>
  <ul><li><strong>保留：</strong>期初负净资产、支持计划与实际执行分别核；上涨不能代替整改证据。</li><li><strong>修正：</strong>不能只沿用4月拟定增的静态描述。9月原定增终止并出现预重整与投资人；10月底首期经营借款已收到。</li><li><strong>尚不能确定：</strong>各公告的净价格贡献、期间全部催化，以及重整最终结果。单一案例不晋级为通用经验。</li><li><strong>等待新证据：</strong>正式受理、法院批准、投资款支付、股份登记、重整执行和后续审计净资产；每个阶段分别确认。</li></ul>
  <details><summary>核验范围与剩余缺口</summary><p>{d.counts.catalog_rows}条目录中选读{d.counts.pdf_files}份原件共{d.counts.pdf_pages}页；{d.counts.event_groups}组事项，{d.counts.complete_windows}个完整窗口、{d.counts.incomplete_windows}个未满窗口。</p><p>含起点的{d.crosscheck.stock_daily_points}个西旅前复权收盘、两指数{d.crosscheck.official_index_daily_points}个官方精度收盘跨渠道一致；指数未取整差异{d.crosscheck.unrounded_index_differences.length}处保留。</p>{d.boundaries.map(t=><p key={t}>{t}</p>)}{d.crosscheck.sources.map(s=><p key={s.key}><a href={s.url} target="_blank" rel="noreferrer">{s.key} 原始行情来源</a></p>)}</details>
 </section>
}
