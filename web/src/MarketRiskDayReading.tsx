import {percent} from './readingFormat'
type Props={date:string;advancingPct:number;medianPct:number;streak:number;fiveDayPct:number|null;priceBound:boolean}
export function MarketRiskDayReading({date,advancingPct,medianPct,streak,fiveDayPct,priceBound}:Props){
 const participation=advancingPct<50?'上涨参与不足半数': '上涨参与至少达到半数'
 const typical=medianPct<0?'个股中位数仍在下跌':medianPct>0?'个股中位数上涨':'个股中位数持平'
 return <aside aria-label="当天风险怎样理解">
  <h4>{date}：先读市场，再决定是否承担更多风险</h4>
  <p className="reading-lead">{participation}，{typical}。{priceBound&&fiveDayPct!==null?`指数近5日${percent(fiveDayPct)}。`:'指数近5日窗口未取得可合并数值。'}{streak>1?`参与不足已连续${streak}日，应把持续性与单日跌幅一起看。`:streak===1?'今天开始参与不足，尚不能据一天判断持续恶化。':'连续参与不足计数归零，但一天改善尚不足以证明风险解除。'}</p>
  <details><summary>把市场观察变成行动前，还要核对什么？</summary>
   <p>若准备加仓，先核对下方同日跌停和ST退出压力是否也在扩散，再检查自己的ST集中度、可用现金与还能承受的账户回撤。这里未取得你的当前持仓，不能据此给出个人仓位。</p>
   <p>待检验的纪律：趋势与参与面一起恶化时，暂停新增高风险暴露并复查集中持仓；退出压力同步上升时，优先检查已有仓位的减持可行性。它们是研究建议，尚无已验证的触发阈值、交易成本或收益保证。</p>
   <p>什么会改变判断：连续参与面改善、大跌比例收敛且退出压力缓和，会支持重新评估；只出现指数反弹、个股利好或单日跌停减少，证据仍不充分。缺少限价数据表示未知，不能当作退出压力已解除。</p>
   <p>不同指标可能描述同一次下跌，不按红灯数量相加为危机概率。波动升高也不等于方向一定向下。历史资料事后取得，本页不是实时预警。</p>
  </details>
 </aside>
}
