import type {MarketStageExperience} from './stRegimeTypes'
import {recoveryPath,endpointSensitivity} from './recoveryPathCalculation'
export function STRecoveryPath({data}:{data:MarketStageExperience}){
 const path=recoveryPath(data)
 const sensitivity=endpointSensitivity(data)
 if(!path)return <p role="status">连续价格路径暂未通过核对，不能据此判断反弹后是否回本。</p>
 return <section aria-label="反弹与回本的区别">
  <h3>8月反弹后，回到7月起点了吗？</h3>
  <p>在五段都通过核价的同一{path.members}家公司中，7月下跌{path.julyLosers}家；其中{path.augustRose}家在8月上涨，但到8月底只有{path.recovered}家回到或超过7月3日的价格。上涨与收复此前跌幅，是两个问题。</p>
  <p>8月底高于7月3日起点的{path.augustPositive}家，到11月19日仍高于起点的有{path.stillPositive}家。这说明修复能否保住，需要继续追踪，不能用一个上涨月份替代后续判断。</p>
  <table className="regime-table"><caption>同一批公司，相对7月3日收盘的累计路径</caption><thead><tr><th>截至</th><th>高于起点</th><th>持平</th><th>低于起点</th><th>累计涨跌中位数</th></tr></thead><tbody>{path.summaries.map(s=><tr key={s.through}><th>{s.through}</th><td>{s.positive}</td><td>{s.zero}</td><td>{s.negative}</td><td>{s.median.toFixed(2)}%</td></tr>)}</tbody></table>
  <p>这是六个日期都有核价通过数据的事后交集，不是7月事前可选出的组合；原150家中其余11家没有填成零收益。复权价格变化不等于账户收益，也不证明制度或某一公告造成了行情。</p>
  {sensitivity&&<details><summary>只选完整记录的139家，会改变结论吗？</summary><p>再做一个对照：保留原150家，只要求7月3日起点与各截止日终点通过核价，不要求中间四个日期都齐全。各截止日可比数量不同，仍不填补缺价。</p><table className="regime-table"><caption>同一起点，不同完整性要求下的累计涨跌</caption><thead><tr><th>截至</th><th>六日期共同139家中位数</th><th>仅起终点通过家数</th><th>仅起终点中位数</th><th>仍排除／原150家</th></tr></thead><tbody>{sensitivity.map(s=><tr key={s.through}><th>{s.through}</th><td>{s.commonMedian.toFixed(2)}%</td><td>{s.members}</td><td>{s.median.toFixed(2)}%</td><td>{s.excluded}／150</td></tr>)}</tbody></table><p>8月底与9月底，共同139家中位数恰好为零；放宽到起终点核价子样本后略为负数。因此应说“典型价格接近起点”，不能把回本写成全体事实。两种口径到11月19日都约跌21%，但接近并不证明其余缺价没有偏差。</p></details>}
  <details><summary>怎样计算，逐家公司是否一致？</summary><p>每家公司都用“当日复权价格 ÷ 7月3日复权价格 − 1”计算累计变化，再统计分布；不把月度中位数相加。相邻段共用同一端点；持平判断容差为十亿分之一个百分点，仅消除浮点误差。</p><table className="regime-table"><caption>139家连续价格路径（%）</caption><thead><tr><th>代码</th>{path.summaries.map(s=><th key={s.through}>{s.through}</th>)}</tr></thead><tbody>{path.rows.map(r=><tr key={r.symbol}><th>{r.symbol}</th>{r.cumulative.map((v,j)=><td key={j}>{v.toFixed(2)}</td>)}</tr>)}</tbody></table></details>
 </section>
}
