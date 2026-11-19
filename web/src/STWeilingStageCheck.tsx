import {useState} from 'react'
import type {RegimeEvent} from './stRegimeTypes'
type Source={url:string;title:string;published_on:string;pages:number;sha256:string}
export type WeilingStageCheck={through:string;symbol:string;rows:{id:string;title:string;published_on:string;document_dated_on:string;change:string;pages:number[];effective_or_scheduled_on:string|null;source:Source;observation:RegimeEvent['observation']}[];meeting:{scheduled_on:string;time:string;state_at_cutoff:string;reminder:Source;reminder_pages:number[];reminder_printed_on:string;original_published_on:string};adviser:{source:Source;pages:number[];report_start:string;report_end:string;document_dated_on:null;scope:string};counts:{pdf_files:number;pdf_pages:number;timeline_stages:number;meeting_matters:number};boundary:string}
const pct=(n:number|null)=>n==null?'窗口未满或缺价':`${n>0?'+':''}${n.toFixed(2)}%`
export function STWeilingStageCheck({data:d}:{data?:WeilingStageCheck|null}){
 const [window,setWindow]=useState('5')
 if(!d)return null
 return <section className="reading-current-observation" aria-label="威领控制权与赠款阶段核对">
  <p className="reading-kicker">补证 · 截至{d.through}已公开材料</p>
  <h4>控制权已经变更，赠款仍待审议和履约</h4>
  <p>要约过户时只有6.12%持股，公司当时明确控制权未变。后来持股增加、董事会改选，才披露自11月4日起变更控制权。不能把后来的完成状态提前放到10月。</p>
  <p>下一次具体核对点：{d.meeting.scheduled_on} {d.meeting.time}拟审议赠款及担保；关联股东回避。安排开会不等于议案通过，议案通过也还要核其他生效条件、赠款到账与贷款实际放款。</p>
  <details className="reading-disclosure"><summary>沿四个阶段查看原件与当时状态</summary>{d.rows.map(r=><article key={r.id}><h5>{r.published_on}披露 · {r.title}</h5><p>{r.change}</p><p className="reading-caption">文件落款{r.document_dated_on}{r.effective_or_scheduled_on&&`；另核生效或安排日${r.effective_or_scheduled_on}`}。</p>{r.pages.map(page=><p key={page}><a href={r.source.url+'#page='+page} target="_blank" rel="noreferrer">{r.source.title} · 第{page}页 ↗</a></p>)}</article>)}<p>11月18日提示性公告（落款{d.meeting.reminder_printed_on}）重申同一会议，不新增一次审议通过：</p>{d.meeting.reminder_pages.map(page=><p key={page}><a href={d.meeting.reminder.url+'#page='+page} target="_blank" rel="noreferrer">会议提示原件 · 第{page}页 ↗</a></p>)}</details>
  <details className="reading-disclosure"><summary>披露之后，股价与市场是否同向？</summary><p>从披露日或此前最近交易日收盘起算，复用已有提供方行情；这不是最早反应或公告净影响。本轮没有新增10月全部价格的跨渠道认证。</p><label>公告后观察窗口 <select value={window} onChange={e=>setWindow(e.target.value)}><option value="5">后5个交易日</option><option value="20">后20个交易日</option></select></label><div className="regime-scroll"><table className="regime-table" aria-label={`威领阶段披露后${window==='5'?'五':'二十'}交易日对照`}><thead><tr><th>披露阶段 / 共同日期</th><th>个股</th><th>主板ST</th><th>中证全指</th></tr></thead><tbody>{d.rows.map(r=>{const w=r.observation.windows[window];return <tr key={r.id}><th>{r.title}<small>{r.observation.anchor} → {w.through??'窗口未满'}</small></th><td>{pct(w.stock_pct)}</td><td>{pct(w.st_pct)}</td><td>{pct(w.market_pct)}</td></tr>})}</tbody></table></div><p>11月6日控制权公告与7日会议通知的行情观察起点相同，不算两次独立行情验证。</p></details>
  <details className="reading-disclosure"><summary>督导报告能证明到哪一步？</summary><p>{d.adviser.scope}</p><p>报告期{d.adviser.report_start}—{d.adviser.report_end}；11月12日目录披露，签署页确切日期未核得。第5页回顾要约、第13页另列后续变化，不能因报告晚披露就将全部核查范围扩到11月。</p>{d.adviser.pages.map(page=><p key={page}><a href={d.adviser.source.url+'#page='+page} target="_blank" rel="noreferrer">督导报告 · 第{page}页 ↗</a></p>)}</details>
  <p className="reading-caption">新增{d.counts.pdf_files}份{d.counts.pdf_pages}页，整理为{d.counts.timeline_stages}个阶段，其中两份会议通知归为同一待审事项。{d.boundary}</p>
 </section>
}
