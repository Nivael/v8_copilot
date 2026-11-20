import packet from './stLimitStreaks.json'
import qihuan from './qihuanOHLCCrosscheck.json'
import {QihuanOHLCCrosscheck} from './QihuanOHLCCrosscheck'
import source from './stLimitCohorts.json'
import {useState} from 'react'
const labels:Record<string,string>={close_at_down:'连续收盘达到下限',one_price_down:'连续全天同价跌停'}
export function STLimitStreaks({groupKey}:{groupKey:string}){
 const [metric,setMetric]=useState('close_at_down')
 if(packet.source_evidence_sha256!==source.evidence_sha256)return <p role="status">连续状态与逐日限价来源不对应，暂不合并。</p>
 const g=packet.reading.groups.find(g=>g.key===groupKey)
 if(!g)return <p role="status">未找到该组连续状态，暂不补值。</p>
 const qihuanBound=qihuan.cohort_evidence_sha256===source.evidence_sha256&&!qihuan.reading.new_day.one_observed_price
 const stats=g.metrics.find(m=>m.metric===metric)!,runs=g.runs.filter(r=>r.metric===metric&&r.observed_sessions>=2)
 return <details className="reading-disclosure"><summary>连续出现时，窗口里能确认几天？</summary><p>截至{packet.reading.through}的九日窗口内，本组有{g.metrics[0].continuous_companies}家公司连续至少2日收盘达到供应商下限，最长已观察{g.metrics[0].longest_observed_sessions}日；连续全天同价跌停为{g.metrics[1].continuous_companies}家公司，最长已观察{g.metrics[1].longest_observed_sessions}日。两种状态分别看，不相加。</p>
 <div className="reading-purpose-switch" role="group" aria-label="连续状态口径">{Object.entries(labels).map(([key,label])=><button key={key} type="button" aria-pressed={metric===key} onClick={()=>setMetric(key)}>{label}</button>)}</div>
 <p>{groupKey==='daily_members'?'每日名单主板组':'固定150只原始样本'} · {labels[metric]}：{stats.continuous_blocks}段，涉及{stats.continuous_companies}家公司。下表只列至少连续2日，单日片段仍在来源中保留。</p>
 <div className="learning-table-wrap"><table className="market-pressure-table"><caption>{labels[metric]}：已观察长度与未核边界</caption><thead><tr><th>公司</th><th>窗口内连续日期</th><th>已观察长度</th><th>之后是否已结束？</th></tr></thead><tbody>{runs.map(r=><tr key={r.symbol+r.dates[0]}><th>{r.name}<small>{r.symbol}</small></th><td>{r.dates[0]}至{r.dates[r.dates.length-1]}</td><td>{r.observed_sessions}个交易日{r.left_boundary_unknown&&<small>左边界未知，不能当完整起点</small>}</td><td>{r.symbol==='000826.SZ'&&metric==='one_price_down'&&qihuanBound?'20日官网日线已非全天同价，右边界已补核':r.ongoing_at_cutoff?'19日仍满足，20日状态未核':r.right_boundary_unknown?'后接未核配/不在组内的日期，不能确认结束':'下一交易日已观察到不满足该状态'}{r.right_boundary_unknown&&!(r.symbol==='000826.SZ'&&metric==='one_price_down'&&qihuanBound)&&<small>不是已经结束的完整段</small>}</td></tr>)}</tbody></table></div>
 <p>启环11月16—19日收盘连续达到下限，但全天同价只连续出现在18—19日；瑞茂同为4日收盘触限，没有连续两日全天同价。收盘触限与全天同价不能互换，也不能由这些记录判断某笔委托是否可成交。</p>
 <QihuanOHLCCrosscheck/><details><summary>连续段怎样计数，哪些仍未知？</summary><p>{packet.reading.boundary}</p><p>同股两次触限中间若有已观察的非触限日，不能拼成连续；若中间缺价，只能拆成可观察片段，不能据此确认真实中断。本组{g.unpaired_observations}个成员证券日未配对，不记为没有跌停。完整源中同时保留单日片段。</p><p><a href={'/runs#research-'+packet.research_run_id}>查看连续状态与未知边界研究 →</a></p></details></details>
}
