import {useState} from 'react'
import packet from './breadthWaitComparison.json'
import alignment from './stBreadthAlignment.json'
import {percent} from './readingFormat'

export function BreadthWaitComparison(){
 const r=packet.reading
 const [first,setFirst]=useState(r.episodes[r.episodes.length-1].first)
 if(packet.alignment_evidence_sha256!==alignment.evidence_sha256)return <p role="status">等待时点比较与同窗来源尚未对应，需重新核对。</p>
 const episode=r.episodes.find(e=>e.first===first)!
 const short=r.episodes.filter(e=>e.observed_weak_sessions<3).length
 return <details className="reading-disclosure"><summary>更早看一两天，会多看到什么、错过什么？</summary>
 <p>共同窗口{r.start}至{r.through}，共{r.observed_sessions}个交易日，有{r.episodes.length}段可观察的偏弱片段，{short}段不足三日。首段左边界未知，不能确认它真的只持续一日。短片段没有形成三日条件，也不代表随后没有下跌风险。</p>
 <p>选择一段，比较第一、第二、第三日收盘时已发生的变化，以及各自随后行情。每个后窗起点不同，不能用它们直接排出哪种等待方式更好。</p>
 <label>选择偏弱片段<select value={first} onChange={e=>setFirst(e.target.value)}>{r.episodes.map(e=><option key={e.first} value={e.first}>{e.first}起 · 已见{e.observed_weak_sessions}日{e.left_boundary_unknown?' · 起点未知':''}{e.ongoing_at_cutoff?' · 截止仍持续':''}</option>)}</select></label>
 <p>从{episode.anchor}收盘作比较锚点；偏弱记录至{episode.last_observed_weak}。{episode.left_boundary_unknown?'这只是覆盖窗口内首日，窗口之前是否已经偏弱未知。':''}{episode.ongoing_at_cutoff?'到共同截止日仍在持续，最终长度未知。':''}</p>
 <div className="learning-table-wrap"><table className="market-pressure-table"><caption>同一片段的不同观察时刻；此前变化与随后变化分开</caption><thead><tr><th>等到哪一天</th><th>此前ST／大盘</th><th>随后完整5日ST／大盘</th><th>窗口状态</th></tr></thead><tbody>{episode.checks.map(c=><tr key={c.wait}><th>第{c.wait}日<small>{c.formed?c.date:'未形成'}</small></th><td>{c.formed?`${percent(c.already_st_pct)}／${percent(c.already_market_pct)}`:'—'}</td><td>{c.formed&&c.following_sessions===5?`${percent(c.five_st_pct)}／${percent(c.five_market_pct)}`:'—'}</td><td>{!c.formed?'该段未观察到此条件':c.following_sessions===5?`完整5日，至${c.through}`:`仅${c.following_sessions}日，至${c.through}；完整5日留空`}{c.formed&&c.following_sessions!==5&&<small>截至已有后窗：{percent(c.partial_st_pct)}／{percent(c.partial_market_pct)}</small>}</td></tr>)}</tbody></table></div>
 <p>{r.boundary} ST是动态等权参考，不是你的账户，也不包括实际交易成本；这些片段不增加独立经验验证次数。</p>
 <p><a href={'/runs#research-'+packet.research_run_id}>查看完整片段与来源研究 →</a></p>
 </details>
}
