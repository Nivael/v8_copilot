import {useState} from 'react'
import {STLimitStreaks} from './STLimitStreaks'
import packet from './stLimitCohorts.json'
import alignment from './stBreadthAlignment.json'
export function STLimitCohorts(){
 const [key,setKey]=useState('daily_members')
 if(packet.alignment_evidence_sha256!==alignment.evidence_sha256)return <p role="status">整组限价与同窗来源不对应，需重新核对。</p>
 const r=packet.reading,g=r.groups.find(g=>g.key===key)!
 const peak=g.days.reduce((a,b)=>b.close_at_down>a.close_at_down?b:a)
 return <details className="reading-disclosure"><summary>把限价核到整个样本后，压力怎样变化？</summary>
 <p>{r.start}至{r.through}，每日名单主板组收盘达到供应商下限最多出现在{r.groups[0].days.reduce((a,b)=>b.close_at_down>a.close_at_down?b:a).date}；全天同价且达到下限的记录出现在11月18日、19日。收盘触限、日内触限和全天同价是不同维度，五只关注股的观察不能代表整个样本。</p>
 <div className="reading-purpose-switch" role="group" aria-label="限价样本范围"><button type="button" aria-pressed={key==='daily_members'} onClick={()=>setKey('daily_members')}>每日名单主板组</button><button type="button" aria-pressed={key==='fixed150'} onClick={()=>setKey('fixed150')}>固定150只原始样本</button></div>
 <p>{key==='daily_members'?'按保存供应商各日ST名单筛选主板，不含科创、创业和北交所；仍缺完整官方法定名录交叉核实。':'固定7月3日的150只主板样本，包含后来离开ST的公司，不能把整组称为当日ST。'} 本组峰值{peak.date}，{peak.close_at_down}/{peak.paired}只收盘达到下限。</p>
 <div className="learning-table-wrap"><table className="market-pressure-table"><caption>{key==='daily_members'?'每日名单主板组':'固定150只'}：实际限价配对，缺价保留</caption><thead><tr><th>日期</th><th>成交配对／成员</th><th>收盘达到下限</th><th>日内触下限</th><th>全天同价跌停</th><th>未配对</th></tr></thead><tbody>{g.days.map(d=><tr key={d.date}><th>{d.date}</th><td>{d.paired}／{d.members}</td><td>{d.close_at_down}只<small>{d.paired?(d.close_at_down/d.paired*100).toFixed(1)+'%':'未知'} · 分母{d.paired}</small></td><td>{d.touch_down}只</td><td>{d.one_price_down}只</td><td>无日线{d.missing_daily}只<small>有成交但未核配{d.unresolved_trading}只；零量日线{d.nontrading_daily}只</small></td></tr>)}</tbody></table></div>
 <p>“实际限价”指保存供应商逐证券日返回，不是统一跌幅推算。日内最低触下限包括收盘仍在下限的股票，各列不能相加。全天同价且在下限也不直接证明某笔委托无法成交；缺日线不记为没有跌停。</p>
 <STLimitStreaks groupKey={key}/><details><summary>全天同价记录、缺价与原件范围</summary><ul>{g.one_price_rows.map(x=><li key={x.symbol+x.date}>{x.date} · {x.name||x.symbol} · {x.symbol} · 收盘/下限{x.close}/{x.down_limit}元</li>)}</ul><p>未配对股票：{[...new Set(g.unresolved_rows.map(x=>x.symbol))].join('、')}。完整逐日缺价仍保留，不能仅因没有日线就认定停牌或摘牌。</p><p>{r.boundary}</p><p>27份保存返回：九日各有名单、原始日线与限价；来源日期和字段、原字节摘要、证券唯一性、价格范围与前收一致性均核。研究来源摘要<code>{packet.evidence_sha256}</code>；未认证11月20日限价、市场队列或执行成本。</p><p><a href={'/runs#research-'+packet.research_run_id}>查看两组逐日配对与原件研究 →</a></p></details>
 </details>
}
