import {useState} from 'react'
import data from './signalNextOpenReading.json'
import early from './earlySignalOpenReading.json'
import earlyLimits from './earlySignalLimitReading.json'
import split from './longNextCloseReading.json'
import cohorts from './stLimitCohorts.json'
import market from './marketDailyLimits.json'
import {percent} from './readingFormat'
export function SignalNextOpenReading(){
 const [day,setDay]=useState(data.next_session)
 const bound=data.signal_evidence_sha256===split.evidence_sha256&&data.cohort_evidence_sha256===cohorts.evidence_sha256&&data.market_scope_evidence_sha256===market.evidence_sha256&&early.signal_evidence_sha256===split.evidence_sha256&&early.input_asset_sha256===data.input_asset_sha256&&earlyLimits.early_ohlc_evidence_sha256===early.evidence_sha256&&earlyLimits.signal_evidence_sha256===split.evidence_sha256
 if(!bound)return <p role="status">下一开盘资料与原提示、限价来源未对应，暂不展示。</p>
 const dates=[...new Set(earlyLimits.rows.map(r=>r.next_session)),data.next_session]
 const latest=day===data.next_session
 const rows=latest?data.focus:earlyLimits.rows.filter(r=>r.next_session===day)
 const mubang=rows.find(r=>r.symbol==='603398.SH')
 const baoxin=rows.find(r=>r.symbol==='002514.SZ')
 return <details><summary>六次提示后，五只跟踪比较股的开盘怎样？</summary><section aria-label="提示后下一开盘核对">
  <label>查看哪一天的下一开盘？ <select aria-label="提示后开盘观察日" value={day} onChange={e=>setDay(e.target.value)}>{dates.map(d=><option key={d} value={d}>{d}</option>)}</select></label>
  {latest?<p className="reading-lead">{day}，这五只股票都有开盘报价，日内最低价均高于各自实际下限。它说明当日并非全天封在下限，仍不能证明你的委托一定能成交。</p>:<p className="reading-lead">{day}，五股原价开高低收已在保存主源与腾讯记录间逐项核同。并与保存的逐股实际限价配对。开盘、盘中触及和收盘是否仍在下限，分别列出。</p>}
  <p>六次提示后的五股开盘报价现均有保存原件：早期五次共25个报价位置经两渠道核同，实际限价也已配对；17日保留此前配对。两渠道不证明底层供数独立，25个位置也不是25次独立验证。五股是既有跟踪比较对象，不代表全部ST或你的持仓；联光等当前简称不回填当时ST身份，思科瑞为科创板，不并入主板ST组。</p>
  <p className="reading-table-scroll-hint">表格可左右滑动，查看全部报价。</p>
  <div className="learning-table-wrap"><table className="market-pressure-table"><caption>{day}报价，单位元；有报价不等于已成交退出</caption><thead><tr><th>比较对象</th><th>开盘与前收参考</th><th>当日实际下限</th><th>日内区间与收盘</th></tr></thead><tbody>{rows.map(row=><tr key={row.symbol}><th>{row.label}<small>{row.symbol}</small></th><td>{row.status==='paired'||row.status==='two_channel_ohlc_match'?<>{row.open}<small>前收参考{row.pre_close}</small><small>{percent(row.open_vs_reference_pct)}</small></>:'报价未核'}</td><td>{row.down_limit}<small>{row.open_at_lower?'开盘在下限':'开盘高于下限'}</small><small>{row.touched_lower?(row.close_at_lower?'触及且收盘仍在下限':'盘中触及，收盘离开'):'日内未触及下限'}</small></td><td>{row.low??'未知'}—{row.high??'未知'}<small>收盘{row.close??'未知'}</small></td></tr>)}</tbody></table></div>
  {day==='2026-07-21'&&mubang?.close_at_lower&&baoxin?.touched_lower&&!baoxin.close_at_lower&&<p>这一天要特别留意：沐邦开盘相对前收参考已跌约{Math.abs(mubang.open_vs_reference_pct).toFixed(2)}%，收盘在下限；宝馨盘中触及下限，收盘则已离开。提示之后的开盘也可能已承受明显下跌，不能把未封下限当作损失很小或退出已获保证。</p>}
  <p>开盘变化相对当日行情给出的前收参考计算，不直接称为相对上一日原始收盘的收益；除权等参考价差异需要另核。</p>
  {latest?<><ul>{data.groups.map(g=><li key={g.key}>{g.key==='daily_members'?'供应商当日ST主板组':'固定历史150组'}：{g.paired}/{g.members}只成交报价配对，开盘在下限{g.open_at_lower}只，收盘在下限{g.close_at_lower}只；未配对{g.unpaired.length}只，缺行不作零跌停。</li>)}</ul><p>两组重叠，不能相加。收盘在下限不能倒推开盘已封住，开盘未封也不等于所有委托都能成交；日线没有买卖盘队列、委托时点或实际滑点。官方交叉核对只覆盖收盘与前收参考，开盘和实际限价仍为供应商记录。</p></>:<p>早期范围只核五股，不认证当日ST组或全市场。限价来自保存供应商，未取得独立交易所限价原件；报价配对不证明某笔委托成交，盘口、委托时点、滑点和真实成交仍缺。</p>}
  <p>原件均事后取得，不证明当时已实时拿到完整资料，也未校准预警误报率或实际交易效果。</p>
  <details><summary>本次用了哪些保存原件？</summary>{latest?data.sources.map(s=><p key={s.response_sha256}>{s.api_name} · {s.params.trade_date} · <code style={{overflowWrap:'anywhere'}}>{s.response_sha256}</code></p>):<>{early.raw_public_sources.map(s=><p key={s.sha256}><a href={s.url} target="_blank" rel="noreferrer">{s.symbol} 腾讯原价来源 ↗</a> · <code style={{overflowWrap:'anywhere'}}>{s.sha256}</code></p>)}{early.primary_daily_sources.filter(s=>s.trade_date===day).map(s=><p key={s.response_sha256}>主源原件 · {s.trade_date} · <code style={{overflowWrap:'anywhere'}}>{s.response_sha256}</code></p>)}{earlyLimits.sources.filter(s=>s.query.params.trade_date===day.replaceAll('-','')).map(s=><p key={s.response_sha256}>实际限价原件 · {s.query.params.trade_date} · <code style={{overflowWrap:'anywhere'}}>{s.response_sha256}</code></p>)}</>}<a href={'/runs#research-'+(latest?data.research_run_id:earlyLimits.research_run_id)}>查看开盘核对研究记录 →</a></details>
 </section></details>
}
