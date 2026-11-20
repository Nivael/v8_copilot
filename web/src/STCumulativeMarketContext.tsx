import type {MarketStageExperience} from './stRegimeTypes'
import {cumulativeMarketContext} from './recoveryPathCalculation'
export function STCumulativeMarketContext({data}:{data:MarketStageExperience}){
 const rows=cumulativeMarketContext(data)
 if(!rows)return null
 const last=rows[rows.length-1]
 return <section aria-label="累计回撤与大盘对照"><h3>比大盘跌得少，为什么仍会亏很多？</h3><p>从7月3日到11月19日，中证全指累计{last.marketPct.toFixed(2)}%，共同139家个股的累计涨跌中位数为{last.fixedMedian.toFixed(2)}%。中位数相对大盘多{last.relativePP.toFixed(2)}个百分点，但价格仍明显低于起点。“相对抗跌”与“绝对亏损”可以同时发生。</p><p>动态ST参考同期{last.stPct.toFixed(2)}%。它的成员与计算方法不同，不能把它当成139家中位数，也不能当作自己的账户收益。</p><table className="regime-table"><caption>统一从7月3日收盘起算，累计变化（%）</caption><thead><tr><th>截至</th><th>中证全指</th><th>动态ST参考</th><th>共同139家中位数</th><th>个股跑赢大盘／139家</th></tr></thead><tbody>{rows.map(r=><tr key={r.through}><th>{r.through}</th><td>{r.marketPct.toFixed(2)}%</td><td>{r.stPct.toFixed(2)}%</td><td>{r.fixedMedian.toFixed(2)}%</td><td>{r.outperform}／{r.members}</td></tr>)}</tbody></table><p>这里的“跑赢”只指同日起终点累计变化高于中证全指，不要求个股上涨；也没有排除行业、风格或公司事件影响。近期ST相对转弱与7月以来仍相对少跌并不矛盾，比较时须同时写清起点、截止日和对象。</p></section>
}
