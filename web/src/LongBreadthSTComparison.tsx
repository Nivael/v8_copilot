import {LongNextCloseReading} from './LongNextCloseReading'
import {LongBreadthReplay} from './LongBreadthReplay'
import {LongBreadthWaitComparison} from './LongBreadthWaitComparison'
import {useState} from 'react'
import cost from './longConfirmationCost.json'
import packet from './longBreadthSTAlignment.json'
import coverage from './longBreadthCoverage.json'
import {percent} from './readingFormat'
export function LongBreadthSTComparison({priceAsOf}:{priceAsOf:string}){
 const [purpose,setPurpose]=useState<'after'|'before'|'wait'|'daily'>('after')
 if(priceAsOf!==coverage.through)return null
 if(packet.breadth_sha256!==coverage.evidence_sha256)return <p role="status">长窗口广度与ST对照来源不对应，待重新核对。</p>
 const r=packet.reading
 const costBound=cost.alignment_sha256===packet.evidence_sha256
 return <details className="reading-disclosure"><summary>连续转弱后一定继续跌吗？把7—11月一起看</summary>
 <p>不一定。新增历史中，7月20日提示后大盘与ST都上涨；9月4日提示后，大盘下跌而ST略涨。连续偏弱描述了环境，不能单独当作随后必跌的规则。</p>
 <p>沪深广度覆盖{coverage.start}至{coverage.through}共{coverage.sessions}日；ST与官方指数核对共同范围为{r.common_start}至{r.common_through}共{r.common_days}日。全窗口共{r.signal_count}次第三日提示，其中{r.complete_signal_count}次有完整共同后5日，最新1次仅3日，分开阅读。</p>
 <div role="group" aria-label="长窗口阅读目的"><button type="button" aria-pressed={purpose==='after'} onClick={()=>setPurpose('after')}>提示后怎样？</button><button type="button" aria-pressed={purpose==='before'} disabled={!costBound} onClick={()=>setPurpose('before')}>确认时已发生什么？</button><button type="button" aria-pressed={purpose==='wait'} onClick={()=>setPurpose('wait')}>等一二三日有何不同？</button><button type="button" aria-pressed={purpose==='daily'} onClick={()=>setPurpose('daily')}>逐日看当时状态</button></div>
 <p className="reading-table-scroll-hint">表格可左右滑动，查看完整列。</p>
 {purpose==='daily'?<LongBreadthReplay/>:purpose==='wait'?<LongBreadthWaitComparison/>:purpose==='after'?<div className="learning-table-wrap"><table className="market-pressure-table"><caption>全部六次提示：同一提示后的ST与大盘，未满窗口单列</caption><thead><tr><th>第三日提示</th><th>共同后窗</th><th>ST参考</th><th>大盘</th></tr></thead><tbody>{r.signals.map(s=><tr key={s.date}><th>{s.date}</th><td>{s.complete_five?'完整5日':'仅3日，未满5日'}<small>截至{s.through}</small></td><td>{percent(s.st_pct)}</td><td>{percent(s.market_pct)}</td></tr>)}</tbody></table></div>:<><p>这三日变化发生在确认之前：从第一弱日前一交易日收盘，复合到第三日收盘。它不是提前预警或你的账户损失。</p><p>7月20日确认时ST已跌8.39%，随后5日却上涨；9月4日确认时ST仍略涨。确认可能偏晚，也不能由此推出随后必跌。</p><div className="learning-table-wrap"><table className="market-pressure-table"><caption>全部六次确认：此前三日已发生的变化，不是提示后收益</caption><thead><tr><th>确认日</th><th>计算起点</th><th>ST参考</th><th>大盘</th></tr></thead><tbody>{cost.reading.rows.map(s=><tr key={s.signal_date}><th>{s.signal_date}</th><td>{s.anchor}收盘</td><td>{percent(s.already_st_pct)}</td><td>{percent(s.already_market_pct)}</td></tr>)}</tbody></table></div><p>前后两段百分比需要复合，不能直接相加；这里没有比较更早行动的实际成交、踏空代价或最优等待天数。</p><a href={'/runs#research-'+cost.research_run_id}>查看全部确认段与前后复合核对 →</a></>}

 {purpose==='after'&&<LongNextCloseReading/>}
 <p>条件沿用“上涨股票连续3个交易日不足有成交股票一半”，每段只在第三日记一次，未优化参数。上涨不足一半包含平盘，不一定等于多数股票下跌。后窗为事后收盘对照，不是假定当日能按收盘价采取行动。</p>
 <details><summary>新增历史怎样改变了观察，哪些仍不能推出？</summary><p>原窗口从9月4日开始，缺少9月2、3日前序；补齐后才确认9月4日已是第三日。旧窗口及研究保留，新观察不冒充当时已知。7月8日、7月20日和9月4日是新增提示，原三次结果保持。</p><p>动态ST参考逐日成员变化，不能当固定组合或账户收益；暂停交易和缺价按各自来源规则处理。更多历史提示并非独立制度实验，不能由六次提示推危机概率、行动规则或制度净影响。官方指数94个日期按两位小数与主源逐项核同，显示的后窗变化仍按原主源计算。</p><a href={'/runs#research-'+packet.research_run_id}>查看97日来源、全部提示及同窗计算 →</a></details>
 </details>
}
