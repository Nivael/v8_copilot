import {useState} from 'react'
import type {RestatementComparison} from './stRegimeTypes'
const pct=(value:string|null)=>value===null?'—（无共同成交端点）':`${Number(value).toFixed(2)}%`
export function STRestatementComparison({data}:{data?:RestatementComparison|null}){
 const [days,setDays]=useState(5)
 if(!data)return null
 return <section id="st-restatement-comparison" aria-label="财报更正比较" style={{scrollMarginTop:80}}>
  <h2>{data.title}</h2><p>{data.answer}</p>
  <p>资料截至 {data.through} · 四通、百利、岭南 · 三家公司，同一个披露日</p>
  {data.cases.map(c=><article key={c.symbol}>
   <h3>{c.name}：{c.affected}</h3><p><strong>判断怎样更新：</strong>{c.update}</p>
   <p>{c.operations}</p><p><strong>下一步看什么：</strong>{c.watch}</p>
   <details><summary>查看公告依据</summary>{c.refs.map(ref=>{const source=data.source_refs.find(s=>s.announcement_id===ref.id);return source&&<p key={ref.id}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a> · 第{ref.pages.join('、')}页</p>})}</details>
  </article>)}
  <h3>四通：增速提高，为什么不等于多卖了产品？</h3>
  <p>半年收入增速由原披露的 {data.growth_recalculation.original_display_pct}% ，按更正基数重算为 {data.growth_recalculation.corrected_display_pct}%。变化来自上年比较数调低，当期收入没有增加。</p>
  <details><summary>查看计算口径与当时信息边界</summary><p>{data.growth_recalculation.boundary}</p></details>
  <h3>同一时段，股价与市场分别怎样走？</h3>
  <label>公告后市场交易日 <select value={days} onChange={e=>setDays(Number(e.target.value))}><option value={1}>1日</option><option value={5}>5日</option><option value={20}>20日（尚未满）</option></select></label>
  <table><caption>统一从10月27日收盘起算；涨跌描述同期表现，不识别公告净影响。</caption><thead><tr><th>公司</th><th>个股</th><th>ST研究参考线</th><th>中证全指</th><th>观察截止</th></tr></thead><tbody>{data.cases.map(c=>{const w=data.event_windows.find(g=>g.symbol===c.symbol)?.windows.find(w=>w.requested_days===days);return w&&<tr key={c.symbol}><th>{c.name}</th><td>{pct(w.stock_pct)}</td><td>{pct(w.st_pct)}</td><td>{pct(w.market_pct)}</td><td>{w.through} · {w.observed_days}日{w.observed_days<days?'，窗口未满':''}</td></tr>})}</tbody></table>
  <h3>可以留下什么经验？</h3><p>{data.experience.retain}</p>
  <p><strong>还不能得出的结论：</strong>{data.experience.not_supported}</p>
  <details><summary>什么证据会推翻判断？还有哪些限制？</summary><p>{data.experience.falsification}</p><ul>{data.boundaries.map(b=><li key={b}>{b}</li>)}</ul></details>
 </section>
}
