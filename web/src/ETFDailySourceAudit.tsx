import {useState} from 'react'
import {scrollTable} from './tableScroll'
import type {ETFDailyRawReconciliation as Audit} from './types'
import {formatShareCount as shares} from './numbers'

const ready=(data:Audit|undefined)=>data?.availability==='source_reconciled'&&data.exact_source_projection_verified
const time=(value:string)=>new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})

export function ETFDailySourceAudit({sse,szse,target}:{sse?:Audit;szse?:Audit;target:string|null}){
  const groups=[{id:'SSE',label:'沪市',data:sse},{id:'SZSE',label:'深市',data:szse}]
  const options=groups.flatMap(group=>ready(group.data)?group.data!.funds.map(fund=>({id:`${group.id}:${fund.code}`,label:`${group.label} · ${fund.code}`,fund,data:group.data!})):[])
  const [selected,setSelected]=useState(options[0]?.id||'')
  const current=options.find(row=>row.id===selected)
  return <div aria-label="ETF日表原响应核对">
    <h3>日表数值与原响应</h3>
    {groups.map(group=><p key={group.id}>{group.label}：{ready(group.data)?<>已逐条核对 {group.data!.share_observations} 条份额、{group.data!.nav_observations} 条实际返回净值，绑定 {group.data!.source_response_count} 个响应引用。观察窗 {group.data!.start} 至 {group.data!.through}。</>:<>当前未通过原响应核对，不沿用旧数量。</>}</p>)}
    <p>这里验证日表与原响应的对应关系。源端舍入规则、整个基金的日份额范围、最终修订和全窗事件仍待确认，净申赎金额继续未发布。</p>
    {options.length>0&&<details className="market-source-notes"><summary>查看原始小数文本与逐日换算</summary>
      <div className="learning-filters"><label>日表原响应 <select aria-label="ETF原响应基金筛选" value={selected} onChange={e=>setSelected(e.target.value)}>{options.map(row=><option value={row.id} key={row.id}>{row.label}</option>)}{!current&&<option value={selected} disabled>{selected||'上次选择'}（当前未取得）</option>}</select></label></div>
      {!current?<p>当前选择没有通过原响应核对的日表，可切换其他基金；上次记录不继续展示。</p>:<>
        {target!==current.data.through&&<p>当前市场目标 {target||'未确定'} 与本核对终点 {current.data.through} 不同，不合算目标日覆盖。</p>}
        <p>{current.fund.code} 原始返回的小数位分布：{Object.entries(current.fund.fractional_digit_counts).map(([digits,count])=>`${digits}位小数 ${count} 条`).join('；')||'本窗无已核对记录'}。尾零可能省略；本窗出现的小数位数不等于已确认的字段精度或误差上界。</p>
        <p>原文按“万份”公布，右栏只作十进制单位换算，不补回源端省略信息，也不自动加回场外份额。表格可左右滑动，向下滚动查看其余日期；聚焦表格后也可用方向键与翻页键滚动。</p>
        {current.fund.records.length===0?<p>该基金在此窗没有通过核对的日记录，缺失不填零。</p>:<div className="learning-table-wrap market-notice-clauses" role="region" aria-label="可滚动的ETF原始日份额表" tabIndex={0} onKeyDown={scrollTable}><table className="learning-table market-daily-source-table"><colgroup><col style={{width:'19%'}}/><col style={{width:'25%'}}/><col style={{width:'28%'}}/><col style={{width:'28%'}}/></colgroup><thead><tr><th scope="col">所属日期</th><th scope="col">原始返回文本（万份）</th><th scope="col">按公布单位换算（份）</th><th scope="col">原响应与本次取得</th></tr></thead><tbody>{current.fund.records.map(row=><tr key={row.date}>
          <th scope="row">{row.date}</th><td>{row.raw_text}<small>{row.fractional_digits}位小数，仅描述本次返回</small></td><td>{shares(row.shares)}<small>公布值的算术换算</small></td><td><a href={row.source_url} target="_blank" rel="noreferrer">交易所原响应 ↗</a><small>{time(row.observed_at)}（北京时间）</small><details><summary>原响应摘要</summary><code>{row.response_sha256}</code></details></td>
        </tr>)}</tbody></table></div>}
        <p>当前显示 {current.fund.records.length} 条；绑定快照 <code>{current.data.snapshot_digest}</code></p>
        <p>{current.data.note}</p>
      </>}
    </details>}
  </div>
}
