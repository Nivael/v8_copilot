import data from './marketDailyLimits.json'
import coverage from './longBreadthCoverage.json'
import st from './stLimitCohorts.json'
export function DailyMarketLimitPressure({day,trading}:{day:string;trading:number}){
 const row=data.days.find(r=>r.date===day)
 if(data.breadth_sha256!==coverage.evidence_sha256||data.source_cohort_sha256!==st.evidence_sha256||(row&&row.official_trading!==trading))return <p role="status">市场限价与所选日广度或来源未对应，暂不合并展示。</p>
 const hits=row?.limit_counts_in_paired
 return <aside aria-label="同日市场实际限价压力"><h4>同一天，沪深市场实际跌停压力有多广？</h4>
  {row&&hits?<><p>{day}沪深普通A股有成交{row.official_trading}只，全部与供应商逐股实际限价配对；收盘与前收另和官方逐股核同。</p><div className="learning-table-wrap"><table className="market-pressure-table"><caption>同日有成交股票作分母，各项重叠、不相加</caption><thead><tr><th>观察</th><th>家数</th><th>占有成交股票</th></tr></thead><tbody>
   <tr><th>收盘在下限</th><td>{hits.close_at_down}只</td><td>{(hits.close_at_down/row.paired*100).toFixed(2)}%</td></tr>
   <tr><th>日内触下限</th><td>{hits.touch_down}只</td><td>{(hits.touch_down/row.paired*100).toFixed(2)}%</td></tr>
   <tr><th>全天同价在下限</th><td>{hits.one_price_down}只</td><td>{(hits.one_price_down/row.paired*100).toFixed(2)}%</td></tr>
  </tbody></table></div><p>日内触限包含收盘仍在下限，全天同价又是更窄的状态。它们描述不同压力，不能相加成一个风险总数；ST样本与市场重叠，也不能加进市场数量。</p></>:<p>{day}尚无本回放已绑定的沪深普通A股完整成交范围实际限价统计。保留未知，不沿用前一日、不填零；下方ST局部观察不能替代。</p>}
  <details><summary>市场限价如何核对，仍缺什么？</summary><p>目前仅覆盖11月9—19日九个交易日，共46957个成交证券日。范围按官方逐日证券身份确定，包括302132.SZ，未靠常见代码前缀猜测。不含北交所、B股及当日无成交证券。</p><p>供应商日线与限价原件逐股配对，官方收盘及前收逐项核同；实际限价字段尚未取得交易所限价独立认证。不是统一跌幅推算，也不是历史盘口、排队或可成交证明。资料事后取得，不冒称当时实时可得。</p><p>20日与更早日期仍缺同范围限价，不把九日扩称97日完整覆盖。证据摘要：<code style={{overflowWrap:'anywhere'}}>{data.evidence_sha256}</code>。这些是同一阶段的证券日观察，不能当46957次独立策略验证。</p></details>
 </aside>
}
