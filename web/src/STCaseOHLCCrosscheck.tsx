import packet from './stCaseOHLCCrosscheck.json'
import source from './stLimitCohorts.json'
export function STCaseOHLCCrosscheck(){
 if(packet.cohort_evidence_sha256!==source.evidence_sha256)return <p role="status">三家公司跨渠道日线与旧整组来源不对应，待重新核对。</p>
 const r=packet.reading
 return <details className="reading-disclosure"><summary>瑞茂、华幸、东珠：跨渠道核价后，20日有什么不同？</summary><p>三家九日共{r.cases.reduce((n,c)=>n+c.matched_ohlc_values,0)}个开高低收价格与另一行情渠道一致；另有上交所保存原件核对{r.cases.reduce((n,c)=>n+c.sse_close_control_days,0)}个收盘价，覆盖到20日。两种核对范围分开，不把官方收盘当完整OHLC。</p>
 <p>20日三家都不是全天同价；华幸收盘高于19日，瑞茂和东珠低于19日。相近的触限经历没有对应相同的次日价格方向，这仍只是所选案例，不能当统一反弹规律。</p>
 <div className="learning-table-wrap"><table className="market-pressure-table"><caption>三家公司20日新增观察；整组共同窗口仍到19日</caption><thead><tr><th>公司</th><th>19日／20日收盘</th><th>20日最低／最高</th><th>与19日相比</th></tr></thead><tbody>{r.cases.map(c=><tr key={c.symbol}><th>{c.name}<small>{c.symbol}</small></th><td>{c.new_day.previous_observed_close}／{c.new_day.close}元</td><td>{c.new_day.low}／{c.new_day.high}元<small>{c.new_day.one_observed_price?'全天同价':'非全天同价'}</small></td><td>{c.new_day.close_vs_previous==='higher'?'收盘较高':c.new_day.close_vs_previous==='lower'?'收盘较低':'收盘相同'}</td></tr>)}</tbody></table></div>
 <p>这里只比较原始收盘价高低，不是复权收益或公告净影响。瑞茂此前九日没有全天同价；华幸和东珠只在18日出现，不能和启环连续两日混为一谈。</p>
 <details><summary>三家分别核了哪些字段与来源？</summary><p>{r.boundary}</p>{r.cases.map(c=><article key={c.symbol}><h4>{c.name}</h4><p>原始OHLC{c.matched_ohlc_days}日、{c.matched_ohlc_values}个价格；官方收盘{c.sse_close_control_days}日。20日实际下限价未补入，不据此认定封板或实际可退出。</p>{packet.source_refs.filter(s=>s.symbol===c.symbol.slice(0,6)).map((s,i)=><p key={s.sha256}><a href={s.url} target="_blank" rel="noreferrer">{i===0?'原始日线渠道':'上交所收盘控制'} · {c.symbol} ↗</a> · 观察{s.observed_at}；SHA256 <code>{s.sha256}</code>。</p>)}</article>)}<p><a href={'/runs#research-'+packet.research_run_id}>查看三家跨渠道核价研究 →</a></p></details></details>
}
