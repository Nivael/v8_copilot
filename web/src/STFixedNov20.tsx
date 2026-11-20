import packet from './stFixedNov20.json'
import cohort from './stLimitCohorts.json'
import {percent} from './readingFormat'
const names:Record<string,string>={'000016.SZ':'康佳','002122.SZ':'汇洲','002717.SZ':'岭南','002731.SZ':'萃华'}
export function STFixedNov20({priceAsOf,priceDigest}:{priceAsOf:string;priceDigest?:string}){
 if(priceAsOf!==packet.reading.through||priceDigest!==packet.benchmark_source_digest)return null
 if(packet.cohort_evidence_sha256!==cohort.evidence_sha256)return <p role="status">20日固定旧样本与原150只来源不对应，待重新核对。</p>
 const r=packet.reading
 return <details className="reading-disclosure"><summary>11月20日，固定ST旧样本是否跟着大盘下跌？</summary><p className="reading-lead">多数仍跌。固定7月3日的150只旧样本中，{r.paired}只有官方双端成交配对：当日中位数{percent(r.median_one_day_pct)}，{r.advancing}只上涨、{r.declining}只下跌、{r.flat}只平盘；另{r.fixed_members-r.paired}只缺口保留。</p>
 <div className="learning-table-wrap"><table className="market-pressure-table"><caption>{r.anchor}收盘至{r.through}收盘；固定旧样本与大盘</caption><thead><tr><th>观察</th><th>当天变化</th><th>怎么读</th></tr></thead><tbody><tr><th>固定旧样本 · 成交子样本</th><td>算术等权{percent(r.equal_weight_one_day_pct)}<small>中位数{percent(r.median_one_day_pct)}</small></td><td>{r.paired}/{r.fixed_members}只双端成交且参考前收一致</td></tr><tr><th>中证全指</th><td>{percent(r.market_one_day_pct)}</td><td>同一收盘窗口</td></tr><tr><th>跌幅至少5%</th><td>{r.declining_at_least_5pct}/{r.paired}只</td><td>固定跌幅门槛，不是实际跌停数</td></tr></tbody></table></div>
 <p>这{r.paired}只当天等权均值比大盘少跌{r.equal_weight_minus_market_pp.toFixed(2)}个百分点，但大多数仍下跌。不能用一天的相对少跌，推翻此前持续偏弱的解释，也不能把这个旧样本称为20日全部ST。</p>
 <details><summary>四只缺口、配对规则与来源</summary><table className="market-pressure-table"><caption>150只都保留；以下不填零收益</caption><thead><tr><th>公司</th><th>未进入分布的原因</th></tr></thead><tbody>{r.unpaired.map(x=><tr key={x.symbol}><th>{names[x.symbol]||x.symbol}<small>{x.symbol}</small></th><td>{x.status==='missing_quote20'?'20日未取得官方报价；不据此推法律状态':x.status==='nontrading20'?'20日报表无成交，参考价不入收益分布':x.status==='reference_mismatch'?'20日参考前收与19日原价不一致，另列':'缺19日实际成交起点'}</td></tr>)}</tbody></table><p>{r.boundary}</p><p>复用{packet.source_counts.sse_stock_responses}份上交所股票日线原件，以及深市两个日包背后的{packet.source_counts.szse_original_files}份原始文件重放。{r.paired}只20日参考前收与19日官方原始收盘一致；没有把参考差异静默混入。此处算术等权只计算单日，不接成旧动态ST曲线或个人持仓回报。</p><p><a href={packet.benchmark_source.url} target="_blank" rel="noreferrer">同窗中证全指来源 ↗</a> · <a href={'/runs#research-'+packet.research_run_id}>查看150只逐项配对与原件研究 →</a></p></details></details>
}
