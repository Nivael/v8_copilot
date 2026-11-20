import {useState} from 'react'
import type {ExitOutcomes} from './stRegimeTypes'
const labels:Record<string,string>={warning_removed:'撤销风险警示',voluntary_delisting:'主动终止上市',delisting_period_then_delisted:'退市整理后摘牌'}
const pct=(s:string|null)=>s===null?'不计算':`${Number(s).toFixed(2)}%`
export function STExitOutcomes({data}:{data?:ExitOutcomes|null}){
 const [window,setWindow]=useState('recent')
 const [symbol,setSymbol]=useState('000016')
 if(!data)return null
 const selected=data.rows.find(r=>r.symbol===symbol)??data.rows[0]
 const summary=data.removed_return_summary.find(r=>r.window===window)!
 const range=data.rows[0].returns.find(r=>r.window===window)!
 return <section id="st-exit-outcomes" aria-label="14家名单变化结果" style={{scrollMarginTop:80}}>
  <h2>{data.title}</h2><p>{data.answer}</p>
  <p>分类截至2026年11月19日：12家撤销风险警示，1家主动终止上市，1家退市整理后摘牌。名单变化、交易状态、程序与账户结果分别看。</p>
  <label>收益核对窗口 <select value={window} onChange={e=>setWindow(e.target.value)}><option value="recent">11月6日 → 11月19日</option><option value="full">7月3日 → 11月19日</option></select></label>
  <p>12家撤销警示公司：{summary.verified_paired}家通过本窗口核价，{summary.positive}家上涨，中位数{pct(summary.median_pct)}。这是{range.anchor}收盘至{range.through}的同窗收益，<strong>不是各自摘帽后的收益</strong>。</p>
  <table className="regime-table"><caption>保留全部14家，期末状态不能代替退出原因</caption><thead><tr><th>公司</th><th>已核性质</th><th>首次离开提供方ST名单</th><th>对应正式生效或程序阶段</th><th>核价通过收益</th></tr></thead><tbody>{data.rows.map(r=>{const ret=r.returns.find(x=>x.window===window)!;return <tr key={r.symbol}><th><button className="regime-text-link" onClick={()=>setSymbol(r.symbol)}>{r.name} {r.symbol}</button></th><td>{labels[r.classification]}</td><td>{r.provider_first_absent}</td><td>{r.official_effective_or_stage_date}{r.symbol==='002731'?' · 进入退市整理（非摘牌日）':r.symbol==='000016'?' · 主动摘牌':' · 撤销生效'}</td><td>{ret.status==='matched'?pct(ret.certified_return_pct):ret.status==='primary_endpoint_gap'?'缺成交端点，留空':'报价待核，留空'}</td></tr>})}</tbody></table>
  <p>{data.selection_boundary}</p>
  <h3>{selected.name}：查看程序与来源</h3>
  <p>{selected.later_reading??'已核撤销生效与提供方首次缺席日期一致；正式撤销风险警示不等于经营风险全部解除或投资获利。'}</p>
  <details><summary>展开所选公司的公告依据</summary>{selected.facts.map((f,n)=><p key={n}>{f.published_on}：{f.text} <a href={f.source.url} target="_blank" rel="noreferrer">{f.source.title}</a></p>)}{selected.later_sources.map(s=><p key={s.source.url}>后续已核原件：<a href={s.source.url} target="_blank" rel="noreferrer">{s.source.title}</a> · 第{s.pages.join('、')}页</p>)}</details>
  <h3>能留下什么经验？</h3><p>{data.experience}</p>
  <details><summary>仍有哪些缺口，什么会改变判断？</summary><p>{data.boundary}</p><ul>{data.watch.map(w=><li key={w}>{w}</li>)}</ul><p>本轮复用既有公告与行情，没有新增下载或逐页重看全部撤销公告；提供方名单日期一致不等于完整官方每日名单已认证。</p></details>
 </section>
}
