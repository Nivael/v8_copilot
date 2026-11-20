import {DailyMarketLimitPressure} from './DailyMarketLimitPressure'
import {DailySTExitPressure} from './DailySTExitPressure'
import {useState} from 'react'
import data from './longBreadthReplay.json'
import coverage from './longBreadthCoverage.json'
import prices from './longIndexReading.json'
import {percent} from './readingFormat'
export function LongBreadthReplay(){
 const [index,setIndex]=useState(data.rows.length-1)
 const row=data.rows[index]
 const price=prices.rows[index]
 const priceBound=prices.breadth_sha256===data.evidence_sha256&&prices.rows.length===data.rows.length&&prices.rows.every((p,i)=>p.date===data.rows[i].date)
 const windowValue=(n:number|null)=>n===null?'前序收盘不足，未计算':percent(n)
 if(data.evidence_sha256!==coverage.evidence_sha256)return <p role="status">逐日回放与长窗来源未对应，暂不展示。</p>
 return <section aria-label="97日广度逐日回放">
  <h3>选一个收盘日，只读截至这一天的状态</h3>
  <p>先分清市场参与面、当日跌幅和持续时间。这里重建的是历史收盘状态，资料在事后取得，不证明当时已经能拿到这些完整数据，也不代表盘中预警。</p>
  <label>观察日 <select aria-label="长窗广度观察日" value={index} onChange={e=>setIndex(Number(e.target.value))}>{data.rows.map((r,i)=><option key={r.date} value={i}>{r.date}</option>)}</select></label>
  <div role="group" aria-label="逐日回放控制"><button type="button" disabled={index===0} onClick={()=>setIndex(i=>i-1)}>前一交易日</button><button type="button" disabled={index===data.rows.length-1} onClick={()=>setIndex(i=>i+1)}>后一交易日</button></div>
  <p className="reading-lead">{row.date}，有成交股票中{row.advancing_pct.toFixed(1)}%上涨，个股涨跌中位数{percent(row.median_return_pct)}；{row.tail_pct.toFixed(1)}%跌幅至少5%。</p>
  <p>{row.streak?`从${row.weak_start}起，上涨股票在覆盖内连续${row.streak}日不足半数。`:'这一天上涨股票不低于半数，覆盖内连续偏弱计数归零。'}{row.third_day_first_signal?'今天刚达到沿用的连续三日示例条件。':row.streak>3?'三日条件此前已经达到，今天不是新的独立提示。':'尚未在当前连续段形成三日提示。'}</p>
  {priceBound?<aside aria-label="同日指数价格压力"><h4>同一天，指数跌了多深，波动有多大？</h4>
   <p>中证全指{price.date}收盘{price.close.toFixed(2)}点。指数与沪深个股广度的成分范围不同，用同日对照，不混用分母。</p>
   <div className="learning-table-wrap"><table className="market-pressure-table daily-price-pressure-table"><caption>截至所选收盘日，只使用此前价格</caption><thead><tr><th>观察什么</th><th>数值</th><th>怎样理解</th></tr></thead><tbody>
    <tr><th>当日变化</th><td>{windowValue(price.day_pct)}</td><td>当日指数冲击</td></tr>
    <tr><th>近5个交易日</th><td>{windowValue(price.five_day_pct)}</td><td>短期价格变化，与连续偏弱天数一起看</td></tr>
    <tr><th>近20个交易日</th><td>{windowValue(price.twenty_day_pct)}</td><td>较长窗口的累计价格变化</td></tr>
    <tr><th>距近20个收盘高点</th><td>{windowValue(price.from_twenty_close_high_pct)}</td><td>离近期最高收盘多远；不是最大回撤或盘中高点回撤</td></tr>
    <tr><th>近20日实现波动</th><td>{price.twenty_day_realized_annualized_pct===null?'前序收盘不足，未计算':price.twenty_day_realized_annualized_pct.toFixed(2)+'%（年化）'}</td><td>描述已发生的日波动大小，不是危机概率或未来跌幅</td></tr>
   </tbody></table></div>
   <details><summary>指数来源与窗口怎样计算？</summary><p>价格来自三组已保存的中证指数官网原件，97个收盘与65个重叠值核同；官方两位小数精度另算，不改旧研究的较高精度数值。</p><p>n日收益需要n+1个收盘；近20个收盘高点需要20个收盘。实现波动取20个日简单收益的样本标准差，乘√252年化，需要21个收盘。早期不足窗口留空，未借后续价格补齐。</p>{prices.sources.map(source=><p key={source.sha256}><a href={source.url} target="_blank" rel="noreferrer">官方指数原件 ↗</a> · <code style={{overflowWrap:'anywhere'}}>{source.sha256}</code></p>)}<p>计算留档摘要：<code style={{overflowWrap:'anywhere'}}>{prices.evidence_sha256}</code>。资料事后取得，价格变化与波动相互相关，不当多份独立风险验证。</p></details>
  </aside>:<p role="status">指数与广度日期尚未对应，价格压力暂不合并展示。</p>}
  <p>分母为当日有成交{row.trading}只：上涨{row.advancing}、下跌{row.declining}、平盘{row.flat}。另有{row.nontrading}只无成交，不填成平盘；跌幅至少5%的{row.tail}只不等于实际跌停。</p>
  <DailyMarketLimitPressure day={row.date} trading={row.trading}/>
  <DailySTExitPressure day={row.date}/>
  <p>上涨不足一半包含平盘，不必然等于多数股票下跌；三日条件是观察示例，未校准危机概率或仓位。这里没有把后续收益放进当天判断，后续表现请切换“提示后怎样？”核对全部命中和反例。</p>
 </section>
}
