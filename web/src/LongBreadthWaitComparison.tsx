import {useState} from 'react'
import packet from './longBreadthWait.json'
import alignment from './longBreadthSTAlignment.json'
import july from './julyIndexControl.json'
import {percent} from './readingFormat'
export function LongBreadthWaitComparison(){
 const episodes=packet.reading.episodes
 const [first,setFirst]=useState(episodes[episodes.length-1].first)
 if(packet.alignment_sha256!==alignment.evidence_sha256)return <p role="status">长窗等待比较与原提示来源不对应，待重新核对。</p>
 const episode=episodes.find(e=>e.first===first)!
 const julyBound=july.wait_evidence_sha256===packet.evidence_sha256
 return <section aria-label="长窗同终点等待比较"><p>共有{packet.summary.episode_count}段偏弱，其中{packet.summary.short_episode_count}段不足三日。这里按事后完整序列分段，不是假定第一天就知道将持续多久；短片段不等于无风险。</p><label>选择偏弱片段 <select aria-label="选择偏弱片段" value={first} onChange={e=>setFirst(e.target.value)}>{episodes.map(e=><option key={e.first} value={e.first}>{e.first}起 · 连续{e.observed_weak_sessions}日{e.observed_weak_sessions<3?' · 不足三日':''}</option>)}</select></label>
 <p>计算起点：{episode.anchor}收盘；统一终点：{episode.target_end}，即首个偏弱日收盘后的第5个交易日。每行都看这个终点，不是各自提示后的5日。</p>
 <div className="learning-table-wrap"><table className="market-pressure-table"><caption>同一片段同一终点：此前变化与剩余变化分列</caption><thead><tr><th>观察时刻</th><th>此前已发生：ST／大盘</th><th>之后还剩</th><th>剩余变化：ST／大盘</th></tr></thead><tbody>{episode.checks.map(c=>c.formed&&'date'in c?<tr key={c.wait}><th>第{c.wait}日<small>{c.date}</small></th><td>{percent(c.already_st_pct)}／{percent(c.already_market_pct)}</td><td>{c.remaining_sessions}个交易日</td><td>{percent(c.partial_st_pct)}／{percent(c.partial_market_pct)}{!episode.complete&&<small>仅已观察部分</small>}</td></tr>:<tr key={c.wait}><th>第{c.wait}日</th><td colSpan={3}>条件未形成；片段不足{c.wait}日，不当作无风险或零收益。</td></tr>)}</tbody></table></div>
 {episode.first==='2026-07-02'&&(julyBound?<aside aria-label="七月二日指数补核"><p>已补中证全指7月1—9日官方记录，7个收盘与主源按两位小数核同；计算起点、确认日和统一终点均已覆盖。原显示收益仍沿用主源精度，不用官方取整值替换。</p><p>原“7月2日未覆盖”的说明保留在旧研究；本次补核只增加同一片段的来源支持，不增加独立经验验证。</p><a href={july.source.url} target="_blank" rel="noreferrer">中证全指7月官方收盘来源 ↗</a><p><a href={'/runs#research-'+july.research_run_id}>查看新增官方价格与端点核对 →</a></p></aside>:<p>这段使用原保存主源收益；独立官方指数价格控制从7月3日开始，7月2日收益尚不在该交叉核对范围。</p>)}
 {episode.ongoing_at_cutoff&&<p>截至ST共同窗口11月19日仍偏弱；不是这段已经结束的证明。20日广度另有记录，不倒填20日ST。</p>}
 <p>统一终点只消除终点差异，各行剩余天数仍不同。前后变化要复合，不能相加；没有同价成交、现金、再参与和交易成本模型，不能用此排名最优等待天数。</p><a href={'/runs#research-'+packet.research_run_id}>查看全部片段、原各自后5日及复合核验 →</a></section>
}
