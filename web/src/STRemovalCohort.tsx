import {useState} from 'react'
import type {RegimeRemovalCohort,RemovalCohortStats,RemovalCohortWindow} from './stRegimeTypes'
import './STRemovalCohort.css'
const pct=(n:number|null)=>n==null?'未算':(n>0?'+':'')+n.toFixed(2)+'%'
const pp=(n:number|null)=>n==null?'未算':(n>0?'+':'')+n.toFixed(2)+'个百分点'
const gap=(w:RemovalCohortWindow)=>w.status==='insufficient_followup'?'后窗未满（只有'+w.available_market_days+'市场日）':w.status==='insufficient_history'?'前史不足':w.status!=='valid'?'缺实际成交端点':!w.quote_endpoint_supported?'复权端点差异待核':'可配对'
function Distribution({label,stats:s}:{label:string;stats:RemovalCohortStats}){
 return <div className="cohort-distribution"><strong>{label}</strong><div><div className="cohort-distribution-track" role="img" aria-label={label+'：'+s.positive_count+'涨、'+s.negative_count+'跌、'+s.flat_count+'平'}><span className="cohort-up" style={{flex:s.positive_count}}/><span className="cohort-flat" style={{flex:s.flat_count}}/><span className="cohort-down" style={{flex:s.negative_count}}/></div><small>{s.positive_count}涨 / {s.negative_count}跌{s.flat_count>0?' / '+s.flat_count+'平':''} · 中位数{pct(s.median_pct)} · 简单均值{pct(s.mean_pct)}</small></div></div>
}
export function STRemovalCohort({data:d}:{data:RegimeRemovalCohort|null|undefined}){
 const [period,setPeriod]=useState('20')
 if(!d)return null
 const s=d.summaries[period],q=d.quote_summary
 return <section className="regime-removal-cohort" aria-label="摘帽样本同窗横向比较">
  <h4>摘帽后，股价是否普遍继续上涨？</h4>
  <label>前后各看多久 <select aria-label="摘帽组前后比较窗口" value={period} onChange={e=>setPeriod(e.target.value)}>{['5','20','40'].map(n=><option key={n} value={n}>{n}个市场交易日</option>)}</select></label>
  <p>截至{d.through}，{d.cohort_total}只撤销警示股票中，{s.paired_count}只可按同一前后{period}市场日配对：后窗{s.after.positive_count}涨、{s.after.negative_count}跌，{s.after.beat_st_count}只跑赢同期ST参考。另{d.cohort_total-s.paired_count}只仍列在表里，未满窗口或报价差异不当作失败或零收益。</p>
  <Distribution label={'前'+period+'日'} stats={s.before}/><Distribution label={'后'+period+'日'} stats={s.after}/>
  <p>同一批可配对公司中，先涨后跌{s.patterns.positive_to_negative??0}只、先跌后涨{s.patterns.negative_to_positive??0}只、两段都涨{s.patterns.both_positive??0}只、两段都跌{s.patterns.both_negative??0}只{s.patterns.flat_involved?'，另'+s.patterns.flat_involved+'只涉及平盘':''}。京蓝的回撤是其中一种路径，不能推广成统一规律。</p>
  {period==='20'&&<p>同一{s.paired_count}只拉长到后40市场日，变为{d.summaries['40'].after.positive_count}涨、{d.summaries['40'].after.negative_count}跌，{d.summaries['40'].after.beat_st_count}只跑赢ST参考。短窗与长窗不同，先检查起止点，再解释“摘帽后表现”。</p>}
  <p className="reading-caption">这是本期已经摘帽的事后分组，不是全部ST的摘帽成功率。下方前后统计始终使用同一批可配对公司；起点取各股停牌前最后成交收盘，后窗包含停牌市场日，不补成交收益。</p>
  <details><summary>展开12只对照、缺窗与日期依据</summary>
   <p>表内前复权收盘变化沿用原数据；“较大盘/ST”是每股同日期窗口的百分点差，不是公告净贡献。未进入配对统计的行保留原参考值并标原因。</p>
   <div className="regime-scroll"><table className="regime-table"><thead><tr><th>公司</th><th>前{period}日</th><th>后{period}日</th><th>后窗较大盘 / ST</th><th>配对状态</th></tr></thead><tbody>{d.rows.map(r=>{const w=r.windows[period],paired=s.paired_symbols.includes(r.symbol);return <tr key={r.symbol}><th scope="row">{r.name}<small>{r.anchor_name} · {r.symbol}</small></th><td>{pct(w.before.stock_pct)}</td><td>{pct(w.after.stock_pct)}</td><td>{pp(w.after.market_excess_pp)} / {pp(w.after.st_excess_pp)}</td><td>{paired?'已纳入同一配对组':[gap(w.before),gap(w.after)].filter((x,n,arr)=>x!=='可配对'&&arr.indexOf(x)===n).join('；')||'待核'}</td></tr>})}</tbody></table></div>
   <p>可配对组前窗：个股简单均值{pct(s.before.mean_pct)}，各股各自同窗大盘均值{pct(s.before.mean_market_pct)}、ST均值{pct(s.before.mean_st_pct)}；后窗分别为{pct(s.after.mean_pct)}、{pct(s.after.mean_market_pct)}、{pct(s.after.mean_st_pct)}。日期因公司而异，这些均值不是共同日期的可交易组合收益。</p>
   <p>{s.paired_count}家公司只对应{s.date_group_count}组日期窗口，{s.possible_stock_pairs}对公司中{s.overlapping_stock_pairs}对的后窗有重叠。相同市场行情及重叠天数不能当作独立重复实验。</p>
   {d.rows.map(r=>{const w=r.windows[period];return <details key={r.symbol}><summary>{r.name}：核日期、停牌与原件</summary><p>公告{r.announced_on}，停牌{r.suspend_on}，撤销{r.warning_removed==='both'?'两类风险警示':r.warning_removed==='delisting'?'退市风险警示':'其他风险警示'}于{r.effective_on}生效；原件与报价停复牌安排{r.halt_and_resume_match?'一致':'存在冲突，暂停认证'}。</p><p>前窗{w.before.anchor??'历史不足'} → {w.before.through??'未满'}；后窗{w.after.anchor??'待核'} → {w.after.through??'未满'}。后窗{s.days}市场日中有{w.after.stock_traded_days??'待满'}个个股成交日；已知无成交日{w.after.nontrade_dates.join('、')||'本窗未列'}。{gap(w.after)}。</p><p>若改从复牌首日收盘{w.from_resume_close.anchor}起算另{period}日，至{w.from_resume_close.through??'窗口未满'}：个股{pct(w.from_resume_close.stock_pct)}，大盘{pct(w.from_resume_close.market_pct)}、ST{pct(w.from_resume_close.st_pct)}。这是另一个窗口，不能替换上表；其端点报价{w.from_resume_close.quote_endpoint_supported?'相符':'尚未认证'}。</p>{r.facts.map((f,n)=><p key={r.symbol+'-'+n}>{f.text} <a href={f.source.url} target="_blank" rel="noreferrer">{f.source.title} · 第{f.source.page}页 ↗</a></p>)}</details>})}
  </details>
  <details><summary>核报价覆盖、绝味复权差异与其他退出样本</summary>
   <p>{q.valid_responses}份有效响应、{q.quote_points}个收盘点，对应{q.actual_traded_security_days}个实际成交证券日；新取{q.new_responses}份、复用京蓝{q.reused_responses}份。原始收盘{q.raw_agree_companies}/{d.cohort_total}股相符，前复权{q.qfq_agree_companies}/{d.cohort_total}股相符。只取得腾讯一个报价渠道的原始/前复权两口径，不认证底层供数完全独立，也未新增提供商查询。</p>
   <p>绝味食品有{q.qfq_difference_points}个历史日期的前复权差异；原值未覆盖。5日窗虽已有原价，但复权端点不相符，暂不进已核配对组；20/40日还缺后窗。差异原因仍待对应公司行动原件和复权算法核实，不能先解释为舍入误差。</p>
   {d.rows.map(r=><details key={r.symbol}><summary>{r.name}：报价来源与差异</summary>{r.channels.map(c=><div key={c.key}><p><a href={c.source.url} target="_blank" rel="noreferrer">{c.key.endsWith('qfq')?'腾讯前复权':'腾讯原始收盘'} ↗</a>：{c.matched_points}/{c.points}点一致，缺{c.missing_trade_dates.length}个成交日、多{c.extra_nontrade_dates.length}个非成交日、价差{c.price_differences.length}日。冻结时间{c.source.observed_at}；链接可能更新，以冻结响应核对。</p>{c.price_differences.length>0&&<div className="regime-scroll"><table className="regime-table"><thead><tr><th>日期</th><th>原值</th><th>报价</th><th>差额</th></tr></thead><tbody>{c.price_differences.map(x=><tr key={x.date}><td>{x.date}</td><td>{x.original_close}</td><td>{x.checked_close}</td><td>{x.difference}</td></tr>)}</tbody></table></div>}</div>)}</details>)}
   <p>原固定样本的{d.original_exit_total}个移出中，另外{d.excluded.length}个并非摘帽，不混进上述组，也不视作零收益：</p>{d.excluded.map(r=><div key={r.symbol}><p><strong>{r.anchor_name}</strong>：{r.status==='voluntary_delisted'?'主动终止上市':'进入退市整理期'}。样本与缺价仍保留在原复盘。</p>{r.facts.map((f,n)=><p key={r.symbol+'-'+n}><a href={f.source.url} target="_blank" rel="noreferrer">{f.source.title} · 第{f.source.page}页 ↗</a></p>)}</div>)}
  </details>
  <p><strong>下一次怎样用：</strong>先区分警示解除与经营变化，再看同日期市场/ST及长短窗口。不能由已摘帽组的涨跌给全部ST估成功率。</p><p className="reading-caption">{d.what_would_change}</p><details><summary>这组比较能回答到哪一步</summary><p>{d.boundary}</p></details>
 </section>
}
