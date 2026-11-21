import data from './signalNextOpenReading.json'
import split from './longNextCloseReading.json'
import cohorts from './stLimitCohorts.json'
import market from './marketDailyLimits.json'
import {percent} from './readingFormat'
export function SignalNextOpenReading(){
 const bound=data.signal_evidence_sha256===split.evidence_sha256&&data.cohort_evidence_sha256===cohorts.evidence_sha256&&data.market_scope_evidence_sha256===market.evidence_sha256
 if(!bound)return <p role="status">下一开盘资料与原提示、限价来源未对应，暂不展示。</p>
 return <details><summary>11月16日提示后，五只跟踪比较股次日开盘怎样？</summary><section aria-label="提示后下一开盘核对">
  <p className="reading-lead">{data.next_session}，这五只股票都有开盘报价，日内最低价均高于各自实际下限。它说明当日并非全天封在下限，仍不能证明你的委托一定能成交。</p>
  <p>目前只核到六次提示中的这一次：本地已存的九日开高低收与限价原件覆盖17日，其余五次的下一开盘未核。五股是既有跟踪比较对象，不代表全部ST或你的实际持仓；思科瑞为科创板，单列实际限价，不并入主板ST组。</p>
  <p className="reading-table-scroll-hint">表格可左右滑动，查看全部报价。</p>
  <div className="learning-table-wrap"><table className="market-pressure-table"><caption>11月17日报价，单位元；有报价不等于已成交退出</caption><thead><tr><th>比较对象</th><th>开盘与前收参考</th><th>当日实际下限</th><th>日内区间与收盘</th></tr></thead><tbody>{data.focus.map(row=><tr key={row.symbol}><th>{row.label}<small>{row.symbol}</small></th><td>{row.status==='paired'?<>{row.open}<small>前收参考{row.pre_close}</small><small>{percent(row.open_vs_reference_pct)}</small></>:'报价未核'}</td><td>{row.down_limit??'未知'}</td><td>{row.low??'未知'}—{row.high??'未知'}<small>收盘{row.close??'未知'}</small></td></tr>)}</tbody></table></div>
  <p>开盘变化相对当日行情给出的前收参考计算，不直接称为相对上一日原始收盘的收益；除权等参考价差异需要另核。</p>
  <ul>{data.groups.map(g=><li key={g.key}>{g.key==='daily_members'?'供应商当日ST主板组':'固定历史150组'}：{g.paired}/{g.members}只成交报价配对，开盘在下限{g.open_at_lower}只，收盘在下限{g.close_at_lower}只；未配对{g.unpaired.length}只，缺行不作零跌停。</li>)}</ul>
  <p>两组重叠，不能相加。收盘在下限不能倒推开盘已封住，开盘未封也不等于所有委托都能成交；日线没有买卖盘队列、委托时点或实际滑点。官方交叉核对只覆盖收盘与前收参考，开盘和实际限价仍为供应商记录，原件事后取得。</p>
  <details><summary>本次用了哪些保存原件？</summary>{data.sources.map(s=><p key={s.response_sha256}>{s.api_name} · {s.params.trade_date} · <code style={{overflowWrap:'anywhere'}}>{s.response_sha256}</code></p>)}<a href={'/runs#research-'+data.research_run_id}>查看开盘与限价核对记录 →</a></details>
 </section></details>
}
