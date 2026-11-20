import packet from './breadthCommonEnd.json'
import original from './breadthWaitComparison.json'
import {percent} from './readingFormat'

export function BreadthCommonEnd({first}:{first:string}){
 if(packet.alignment_evidence_sha256!==original.alignment_evidence_sha256)return <p role="status">统一终点与原片段来源不对应，需重新核对。</p>
 const ep=packet.reading.episodes.find(e=>e.first===first)
 if(!ep)return <p role="status">未找到对应片段，暂不补值。</p>
 return <section aria-label="统一终点的等待变化"><p>本段统一终点为{ep.target_end}：从首日收盘后数5个交易日，不随等待天数改变。{ep.complete?'已覆盖该终点。':`资料只到${ep.observed_end}，完整终点结果留空。`}</p>
 <div className="learning-table-wrap"><table className="market-pressure-table"><caption>统一至{ep.target_end}；各行剩余天数不同</caption><thead><tr><th>观察时刻</th><th>此前ST／大盘</th><th>此后至统一终点ST／大盘</th><th>剩余窗口</th></tr></thead><tbody>{ep.checks.map(c=><tr key={c.wait}><th>第{c.wait}日<small>{c.formed?c.date:'未形成'}</small></th><td>{c.formed?`${percent(c.already_st_pct)}／${percent(c.already_market_pct)}`:'—'}</td><td>{c.formed&&ep.complete?`${percent(c.remaining_st_pct)}／${percent(c.remaining_market_pct)}`:'—'}</td><td>{!c.formed?'条件未形成，仍保留该段':`${c.remaining_sessions}个交易日，至${ep.observed_end}${ep.complete?'':'；尚未到统一终点'}`}</td></tr>)}</tbody></table></div>
 {ep.complete&&<p>从{ep.anchor}收盘到统一终点，ST参考{percent(ep.total_st_pct)}、大盘{percent(ep.total_market_pct)}。每行此前与此后复合得到同一总变化，两个百分比不能直接相加。</p>}
 <p>{packet.reading.boundary}</p><p><a href={'/runs#research-'+packet.research_run_id}>核对统一终点、计算与来源 →</a></p></section>
}
