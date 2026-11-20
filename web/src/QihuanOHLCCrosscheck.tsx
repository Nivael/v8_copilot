import packet from './qihuanOHLCCrosscheck.json'
import cohort from './stLimitCohorts.json'
export function QihuanOHLCCrosscheck(){
 if(packet.cohort_evidence_sha256!==cohort.evidence_sha256)return <p role="status">启环官网日线与旧整组来源不对应，待重新核对。</p>
 const r=packet.reading,n=r.new_day
 const previous=cohort.reading.groups[0].one_price_rows.find(x=>x.symbol===r.symbol&&x.date===r.paired_through)
 return <aside aria-label="启环官网日线补核"><h4>启环补核：20日已不再全天同价</h4><p>深交所官网日线与此前{r.paired_start}至{r.paired_through}的{r.paired_ohlc_days}日开高低收、共{r.paired_ohlc_values}个价格逐项一致，支持18、19日全天同价的旧观察。</p><p>{n.date}官网日线：开盘{n.open}元、收盘{n.close}元、最低{n.low}元、最高{n.high}元。最高最低不同，已能补明全天同价段在19日后中断；这只更新启环，不推进整组共同窗口。</p>{previous&&<p>20日收盘仍低于19日的{previous.close}元；全天同价结束，不能据此认定价格已经修复。</p>}<details><summary>官网日线能补哪一层，仍缺哪一层？</summary><p>{r.boundary}</p><p>20日收盘高于日内最低价；本轮没有补入20日实际下限价字段，连续收盘触限仍按原九日直接配对范围展示。原“20日未核”记录保留，这里追加单家公司日线更新，不改写旧证据。</p><p><a href={packet.official_source.url} target="_blank" rel="noreferrer">深交所启环日线来源 ↗</a> · 观察{packet.official_source.observed_at}；原件SHA256 <code>{packet.official_source.sha256}</code>。</p><p><a href={'/runs#research-'+packet.research_run_id}>查看官网OHLC交叉核对研究 →</a></p></details></aside>
}
