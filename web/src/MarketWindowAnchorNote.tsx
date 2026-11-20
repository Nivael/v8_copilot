import {useEffect,useRef,useState} from 'react'
import {Link} from 'react-router-dom'
import audit from './marketWindowAnchorAudit.json'

export function MarketWindowAnchorNote({readingReady=true}:{readingReady?:boolean}){
 const [open,setOpen]=useState(()=>window.location.hash==='#market-window-anchor-audit')
 const region=useRef<HTMLElement>(null)
 useEffect(()=>{const reveal=()=>{if(window.location.hash==='#market-window-anchor-audit')setOpen(true)};window.addEventListener('hashchange',reveal);return()=>window.removeEventListener('hashchange',reveal)},[])
 useEffect(()=>{if(open&&readingReady&&window.location.hash==='#market-window-anchor-audit')region.current?.scrollIntoView?.({block:'start'})},[open,readingReady])
 return <section ref={region} className="market-window-anchor-note" aria-label="旧市场复盘窗口核对" id="market-window-anchor-audit">
  <details className="reading-disclosure" open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
   <summary>旧复盘的起点：9月4日与7日能互换吗？</summary>
   <p><strong>不能。−10.61%和−12.80%对应9月4日收盘起点。</strong>9月7日是首个计入收益的交易日，不能改写为从这天收盘开始。</p>
   <table aria-label="同一终点的两种收盘起点"><thead><tr><th scope="col">收盘起点 → 终点</th><th scope="col">中证全指</th><th scope="col">旧ST参考</th></tr></thead>
    <tbody>{audit.rows.map(r=><tr key={r.anchor}><th scope="row">{r.anchor} → {r.through}</th><td>{Number(r.market_pct).toFixed(2)}%</td><td>{Number(r.st_pct).toFixed(2)}%</td></tr>)}</tbody>
   </table>
   <p>9月7日两条序列都上涨。改成7日收盘起算，就跳过了这一天的上涨，后续累计跌幅因而更大。两种窗口都下跌、ST都落后大盘，但具体收益不能混用。</p>
   <p>这里重放的是截至2026年11月5日的旧研究，不是当前行情。ST采用当时保存的参考序列，本轮没有重新逐只核验成员或报价。</p>
   <details><summary>日期、计算与原登记依据</summary>
    <p>累计涨跌＝终点数值÷起点数值−1。中证全指全部保存图表点与官方响应逐点一致；ST按保存参考序列复算。直接端点比值与逐日连乘一致。</p>
    <table aria-label="起终点数值"><thead><tr><th scope="col">日期</th><th scope="col">中证全指收盘</th><th scope="col">ST参考数值</th></tr></thead><tbody>{audit.endpoints.map(r=><tr key={r.date}><th scope="row">{r.date}</th><td>{r.market}</td><td>{r.st}</td></tr>)}</tbody></table>
    <p>早期两条保存记录将起点写为9月7日，后来记录已改为9月4日。原记录各自保留，不能当三次独立验证。</p>
    <p><Link to={'/runs#research-'+audit.corrected_run_id}>查看当时更正后的记录</Link>；{audit.earlier_run_ids.map((id,i)=><span key={id}>{i>0?'、':''}<Link to={'/runs#research-'+id}>早期记录{i+1}</Link></span>)}</p>
    <p><a href={audit.source.official_index_url}>中证全指官方来源</a> · 保存响应SHA256：<code>{audit.source.official_index_response_sha256}</code>。这次没有重新下载。</p>
   </details>
  </details>
 </section>
}
