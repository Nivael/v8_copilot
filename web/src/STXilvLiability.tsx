import {useState} from 'react'
type Window={anchor:string;through:string|null;stock_pct:number|null;st_pct:number|null;market_pct:number|null;requested_days:number;available_days:number;complete:boolean}
type Source={url:string;title:string;published_on:string;document_dated_on:string;announcement_id:string}
export type XilvLiability={through:string;judgment:string;chains:{key:string;group:string;title:string;status:string;reading:string;steps:{source:Source;fact:string;pages:number[];windows:Window[]}[]}[];arithmetic:{claim_requested_sum_excluding_other_costs_yuan:string;cumulative_total_wanyuan:string;not_recognized_losses:boolean};counts:{new_files:number;new_pages:number;chains:number;source_disclosures:number;complete_windows:number;incomplete_windows:number};boundaries:string[];method_promotions:number}
const pct=(n:number|null)=>n==null?'未满窗口':`${n>0?'+':''}${n.toFixed(2)}%`
export function STXilvLiability({data:d}:{data?:XilvLiability|null}){
 const [group,setGroup]=useState('funds'),[requested,setRequested]=useState('old1000'),[stepIndex,setStepIndex]=useState(0)
 if(!d)return null
 const rows=d.chains.filter(c=>c.group===group),chain=rows.find(c=>c.key===requested)??rows[0],step=chain.steps[stepIndex]??chain.steps[0]
 return <section className="regime-reading-section" aria-label="西旅资金与偿债补核">
  <p className="reading-kicker">新增10份原件 · 资金、担保与诉讼分开看</p>
  <h4>支持已有进展，旧债压力仍需跟踪</h4><p>{d.judgment}</p>
  <p>上一轮首期经营借款1000万元实收继续保留。本轮另核两笔旧债展期；1亿元额度、5000万元展期与担保额度，不能相加当作新增现金。</p>
  <div className="regime-tabs" aria-label="选择资金或诉讼"><button aria-pressed={group==='funds'} onClick={()=>{setGroup('funds');setStepIndex(0)}}>资金与担保</button><button aria-pressed={group==='cases'} onClick={()=>{setGroup('cases');setStepIndex(0)}}>诉讼与执行</button></div>
  <div className="regime-scroll"><table className="regime-table"><caption>每行是一条事项链，文件数量不当独立验证次数</caption><thead><tr><th>选择事项</th><th>先看区别</th></tr></thead><tbody>{rows.map(c=><tr key={c.key}><td><button className="regime-text-link" aria-pressed={chain.key===c.key} onClick={()=>{setRequested(c.key);setStepIndex(0)}}>{c.title}</button></td><td>{c.status}</td></tr>)}</tbody></table></div>
  <h4>{chain.title}</h4><p>{chain.reading}</p>
  {chain.key==='claim'&&<p>三项诉请金额算术合计约{(Number(d.arithmetic.claim_requested_sum_excluding_other_costs_yuan)/10000).toFixed(2)}万元，尚不含诉讼等其他费用；这是请求金额合计，不是判定应付款或本期损失。</p>}
  {chain.key==='cumulative'&&<p>四笔较大案件979.80万元，加30笔其他案件154.20万元，核对为1134.00万元。原告、被告及案件阶段不同，不能全当现金流出，也不能与前期已披露重大案件重复累加。</p>}
  <label htmlFor="xilv-liability-step">沿披露顺序看批准或履约</label>
  <select id="xilv-liability-step" value={chain.steps.indexOf(step)} onChange={e=>setStepIndex(Number(e.target.value))}>{chain.steps.map((s,i)=><option key={s.source.announcement_id} value={i}>{s.source.published_on} · {s.source.title}</option>)}</select>
  <p><strong>这一步已确认：</strong>{step.fact}</p>
  <p><a href={step.source.url} target="_blank" rel="noreferrer">查看此步原件 · 第{step.pages.join('、')}页</a> · 披露{step.source.published_on} · 原件署期{step.source.document_dated_on}</p>
  <details><summary>这次披露附近，西旅与市场怎样走？</summary><p>共同起点为{step.windows[0].anchor}收盘；准确披露时刻未核，只作事后比较。同链重复披露不是新的独立案例。</p><div className="regime-scroll"><table className="regime-table"><thead><tr><th>观察窗口</th><th>到哪天</th><th>西旅</th><th>ST参考</th><th>中证全指</th></tr></thead><tbody>{step.windows.map(w=><tr key={w.requested_days}><td>后{w.requested_days}个交易日</td><td>{w.complete?w.through:`截至${d.through}仅${w.available_days}日`}</td><td>{pct(w.stock_pct)}</td><td>{pct(w.st_pct)}</td><td>{pct(w.market_pct)}</td></tr>)}</tbody></table></div></details>
  <details><summary>本轮怎样修正判断，以及还缺什么？</summary><p>保留“进展不等于风险解除”；补入旧债展期及已批准额度，纠正将支持金额相加当现金的读法。新增10份29页分为6条事项链，30个披露窗口中29个完整、1个未满。</p>{d.boundaries.map(b=><p key={b}>{b}</p>)}<p>与原过程9份合计选读19/32份、124页；尚未认证全部事项和11月19日最新法律、余额或代偿状态。期初事实仍46/150，不增加通用经验晋级。</p></details>
 </section>
}
