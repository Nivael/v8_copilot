import packet from './qihuanOHLCCrosscheck.json'
import cohort from './stLimitCohorts.json'
import limits from './qihuanNov20Limits.json'
export function QihuanOHLCCrosscheck(){
 if(packet.cohort_evidence_sha256!==cohort.evidence_sha256)return <p role="status">启环官网日线与旧整组来源不对应，待重新核对。</p>
 const r=packet.reading,n=r.new_day
 const bound=limits.official_sha256===packet.official_source.sha256&&limits.reading.date===n.date&&Number(limits.reading.close)===Number(n.close)
 const previous=cohort.reading.groups[0].one_price_rows.find(x=>x.symbol===r.symbol&&x.date===r.paired_through)
 return <aside aria-label="启环官网日线补核"><h4>启环补核：20日已不再全天同价</h4><p>深交所官网日线与此前{r.paired_start}至{r.paired_through}的{r.paired_ohlc_days}日开高低收、共{r.paired_ohlc_values}个价格逐项一致，支持18、19日全天同价的旧观察。</p><p>{n.date}官网日线：开盘{n.open}元、收盘{n.close}元、最低{n.low}元、最高{n.high}元。最高最低不同，已能补明全天同价段在19日后中断；这只更新启环，不推进整组共同窗口。</p>{previous&&<p>20日收盘仍低于19日的{previous.close}元；全天同价结束，不能据此认定价格已经修复。</p>}{bound&&<p>新增实际限价补核：东方财富报价的交易时间为11月20日15:34:24（北京时间），下限{limits.reading.lower}元、上限{limits.reading.upper}元。最低触及下限，收盘{limits.reading.close}元未收在下限；这一天不能算连续收盘跌停，也不代表当时可以按该价卖出。</p>}<details><summary>官网日线能补哪一层，仍缺哪一层？</summary><p>{r.boundary}</p><p>20日收盘高于日内最低价；旧官网日线研究没有实际下限字段；新增报价在本页另行补核。整组连续状态仍按原九日直接配对范围展示。原“20日未核”记录保留，这里追加单家公司日线更新，不改写旧证据。</p>{bound&&<p><a href="https://quote.eastmoney.com/sz000826.html" target="_blank" rel="noreferrer">东方财富启环报价 ↗</a> · 保存原始返回SHA256 <code>{limits.quote_source.sha256}</code>；公开页面以后会变化，以本次保存原件为准。<a href={'/runs#research-'+limits.research_run_id}>查看20日限价补核研究 →</a></p>}<p><a href={packet.official_source.url} target="_blank" rel="noreferrer">深交所启环日线来源 ↗</a> · 观察{packet.official_source.observed_at}；原件SHA256 <code>{packet.official_source.sha256}</code>。</p><p><a href={'/runs#research-'+packet.research_run_id}>查看官网OHLC交叉核对研究 →</a></p></details></aside>
}
