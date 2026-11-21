import {SignalNextOpenReading} from './SignalNextOpenReading'
import split from './longNextCloseReading.json'
import alignment from './longBreadthSTAlignment.json'
import prices from './longIndexReading.json'
import {percent} from './readingFormat'
export function LongNextCloseReading(){
 if(split.alignment_sha256!==alignment.evidence_sha256||split.index_evidence_sha256!==prices.evidence_sha256)return <p role="status">下一收盘分解与原后窗来源未对应，暂不合并。</p>
 return <details><summary>等到下一交易日收盘，原后窗还剩多少变化？</summary>
  <section aria-label="下一收盘与剩余后窗">
   <p className="reading-lead">同样是提示后5日上涨，中间可能先跌后涨，也可能先涨后跌。7月20日后，大盘首日涨3.46%，余4日跌0.44%；ST首日跌1.86%，余4日涨4.03%。只看合计，会漏掉这段不同的路径。</p>
   <p>这里把上表同一个后窗拆开，终点保持不变。下一收盘只是观察边界，不是假定能够在该价卖出。首日包含隔夜及全天变化，不能单独称为隔夜跳空；也没有重新给剩余段补足5日。</p>
   <div className="learning-table-wrap"><table className="market-pressure-table"><caption>全部六次提示：前一段与剩余段需要复合，不能直接相加</caption><thead><tr><th>提示日与原终点</th><th>到下一收盘已经变化</th><th>从下一收盘到原终点</th></tr></thead><tbody>{split.rows.map(row=><tr key={row.signal_date}><th>{row.signal_date}<small>原终点{row.through}</small><small>{row.complete_five?'完整5日，拆成1＋4日':'未满5日，仅拆成1＋2日'}</small></th><td>{row.next_close}<small>ST {percent(row.st.first_day_pct)}</small><small>大盘 {percent(row.market.first_day_pct)}</small></td><td>剩余{row.remaining_sessions}个交易日<small>ST {row.st.remaining_pct===null?'无剩余观察':percent(row.st.remaining_pct)}</small><small>大盘 {row.market.remaining_pct===null?'无剩余观察':percent(row.market.remaining_pct)}</small></td></tr>)}</tbody></table></div>
   <p>ST是逐日变动成员的参考，不是你的持仓。以上不能证明晚一天减仓的效果；下一开盘仅有下方注明的局部核对，其他日期、盘中委托、盘口排队和成交成本仍缺，也未校准误报率或最优等待天数。大盘两段端点已另对保存的官方指数原件，原后窗结果保持。</p>
   <SignalNextOpenReading/>
   <a href={'/runs#research-'+split.research_run_id}>查看拆分核验与原研究记录 →</a>
  </section>
 </details>
}
