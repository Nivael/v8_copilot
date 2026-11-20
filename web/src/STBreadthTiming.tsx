import timing from './stBreadthTiming.json'
import alignment from './stBreadthAlignment.json'
import {percent} from './readingFormat'
export function STBreadthTiming(){
 if(timing.alignment_evidence_sha256!==alignment.evidence_sha256)return <p role="status">同窗来源变化，确认滞后比较待重核。</p>
 return <details className="reading-disclosure"><summary>等到三日条件成立，前面已经跌了多少？</summary><p>11月16日收盘才形成三日条件。从11日收盘到16日，ST参考已经跌5.59%，大盘已跌4.76%。它确认弱势持续，不能当作下跌前预警。</p><div className="learning-table-wrap"><table className="market-pressure-table"><caption>提示形成前已发生的三日变化，与随后行情分列</caption><thead><tr><th>提示收盘</th><th>前三日的前收锚点</th><th>形成前ST</th><th>形成前大盘</th><th>随后ST／大盘</th></tr></thead><tbody>{timing.reading.rows.map(r=><tr key={r.signal_date}><th>{r.signal_date}</th><td>{r.anchor}<small>首个弱日{r.first_weak_day}</small></td><td>{percent(r.already_st_pct)}</td><td>{percent(r.already_market_pct)}</td><td>{percent(r.following.st_pct)}／{percent(r.following.market_pct)}<small>后{r.following.observed_following_sessions}日，至{r.following.through}{r.following.complete_five?'':'；未满5日'}</small></td></tr>)}</tbody></table></div><p>{timing.reading.boundary}</p><p>确认持续性会付出等待成本；缩短等待是否更好，还要核误报、后续修复及实际执行。这些事后片段尚不能比较不同规则优劣，也不代表你当时的账户损失。</p><p><a href={'/runs#research-'+timing.research_run_id}>查看提示滞后研究 →</a></p></details>
}
