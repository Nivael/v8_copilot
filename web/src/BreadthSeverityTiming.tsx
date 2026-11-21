import {useState} from 'react'
import data from './breadthSeverityReading.json'
import coverage from './longBreadthCoverage.json'
const labels:Record<string,string>={prior_unknown:'前收未知（覆盖起点）',confirmed_at_previous_close:'前收当前偏弱段已连续至少3日',first_confirmed_today:'当天收盘才刚达到3日',current_spell_not_confirmed:'当天收盘连续计数仍未达3日'}
export function BreadthSeverityTiming({expanded=false,asOf}:{expanded?:boolean;asOf?:string}={}){
 const [threshold,setThreshold]=useState(20)
 if(data.breadth_sha256!==coverage.evidence_sha256||data.observations!==coverage.sessions||(asOf!==undefined&&asOf!==data.through))return <p role="status">大跌扩散与连续确认的来源未对应，暂不合并。</p>
 const selected=data.thresholds.find(t=>t.threshold_pct===threshold)!
 const rows=data.days.filter(r=>selected.dates.includes(r.date))
 const july13=data.days.find(r=>r.date==='2026-07-13')
 const content=<section aria-label="当日冲击与连续确认">
  <p className="reading-lead">可能。持续性与当天跌得多广，要分开看。7月13日是覆盖内当前偏弱段第一日，当天约{july13?.tail_pct.toFixed(1)}%的有成交股票跌幅至少5%。未达到当前段三日条件，不能当作此前安全。</p>
  <p>用本次沪深普通A股完整{data.observations}日作事后对照。下方10%、20%、30%只是“大跌股票占有成交股票比例”的并列示例，不是经过校准的危机标准；大跌指当日跌幅至少5%，并非实际跌停。</p>
  <label>大跌扩散示例 <select aria-label="大跌占比示例分界" value={threshold} onChange={e=>setThreshold(Number(e.target.value))}>{data.thresholds.map(t=><option key={t.threshold_pct} value={t.threshold_pct}>至少{t.threshold_pct}%股票当日跌幅达5%</option>)}</select></label>
  <p>满足所选示例的{selected.days}天中：{selected.counts.confirmed_at_previous_close}天在前一收盘仍处于至少三日偏弱段；{selected.counts.first_confirmed_today}天当天收盘才刚确认；{selected.counts.current_spell_not_confirmed}天当天连续计数仍未达三日；{selected.counts.prior_unknown}天前收状态未知。这是状态对照，不是预警命中率。</p>
  <p className="reading-table-scroll-hint">表格可左右滑动，核对日期与计数。</p>
  <div className="learning-table-wrap"><table className="market-pressure-table"><caption>全部符合示例的日期，包含尚未三日确认的情况</caption><thead><tr><th>日期与大跌分布</th><th>前一收盘已知状态</th><th>当天收盘才知道</th></tr></thead><tbody>{rows.map(r=><tr key={r.date}><th>{r.date}<small>{r.tail}/{r.trading}只，{r.tail_pct.toFixed(1)}%</small></th><td>{r.previous_close??'覆盖起点，未知'}<small>{r.previous_streak===null?'无前收计数':`当前段连续计数${r.previous_streak}日`}</small></td><td>{labels[r.confirmation_state]}<small>当日计数{r.streak}日；本段起点{r.weak_start??'无当前偏弱段'}</small></td></tr>)}</tbody></table></div>
  <p>前收已确认，指覆盖内当前段截至前一天仍连续至少三日；不等于一套持续生效的交易规则。当前段未确认，也不表示此前从未出现其他提示，参与面改善后计数会归零。覆盖起点前状态未知，不能反推。</p>
  <p>当天完整广度在收盘后才确定，不能把本表称为下跌发生前的预警。相邻日期及三个示例分界重叠，不算独立实验；这里没有定义或检验误报率、仓位规则及交易收益。</p>
  <a href={'/runs#research-'+data.research_run_id}>查看全部97日状态与示例分界核对 →</a>
 </section>
 return expanded?content:<details><summary>没有三日确认，也可能已经出现大跌扩散吗？</summary>{content}</details>
}
