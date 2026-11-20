import {useState} from 'react'
import data from './longBreadthReplay.json'
import coverage from './longBreadthCoverage.json'
import {percent} from './readingFormat'
export function LongBreadthReplay(){
 const [index,setIndex]=useState(data.rows.length-1)
 const row=data.rows[index]
 if(data.evidence_sha256!==coverage.evidence_sha256)return <p role="status">逐日回放与长窗来源未对应，暂不展示。</p>
 return <section aria-label="97日广度逐日回放">
  <h3>选一个收盘日，只读截至这一天的状态</h3>
  <p>先分清市场参与面、当日跌幅和持续时间。这里重建的是历史收盘状态，资料在事后取得，不证明当时已经能拿到这些完整数据，也不代表盘中预警。</p>
  <label>观察日 <select aria-label="长窗广度观察日" value={index} onChange={e=>setIndex(Number(e.target.value))}>{data.rows.map((r,i)=><option key={r.date} value={i}>{r.date}</option>)}</select></label>
  <div role="group" aria-label="逐日回放控制"><button type="button" disabled={index===0} onClick={()=>setIndex(i=>i-1)}>前一交易日</button><button type="button" disabled={index===data.rows.length-1} onClick={()=>setIndex(i=>i+1)}>后一交易日</button></div>
  <p className="reading-lead">{row.date}，有成交股票中{row.advancing_pct.toFixed(1)}%上涨，个股涨跌中位数{percent(row.median_return_pct)}；{row.tail_pct.toFixed(1)}%跌幅至少5%。</p>
  <p>{row.streak?`从${row.weak_start}起，上涨股票在覆盖内连续${row.streak}日不足半数。`:'这一天上涨股票不低于半数，覆盖内连续偏弱计数归零。'}{row.third_day_first_signal?'今天刚达到沿用的连续三日示例条件。':row.streak>3?'三日条件此前已经达到，今天不是新的独立提示。':'尚未在当前连续段形成三日提示。'}</p>
  <p>分母为当日有成交{row.trading}只：上涨{row.advancing}、下跌{row.declining}、平盘{row.flat}。另有{row.nontrading}只无成交，不填成平盘；跌幅至少5%的{row.tail}只不等于实际跌停。</p>
  <p>上涨不足一半包含平盘，不必然等于多数股票下跌；三日条件是观察示例，未校准危机概率或仓位。这里没有把后续收益放进当天判断，后续表现请切换“提示后怎样？”核对全部命中和反例。</p>
 </section>
}
