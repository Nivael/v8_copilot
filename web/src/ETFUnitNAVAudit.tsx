import {useState} from 'react'
import type {ETFUnitNAVReconciliation as Audit} from './types'
import {scrollTable} from './tableScroll'

const time=(s:string)=>new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})

export function ETFUnitNAVAudit({data,target}:{data?:Audit;target:string|null}){
  const ready=data?.availability==='source_reconciled'&&data.exact_source_projection_verified
  const [selected,setSelected]=useState(data?.funds[0]?.code||'')
  const fund=ready?data.funds.find(f=>f.code===selected):undefined
  return <div aria-label="基金公司单位净值原响应核对">
    <h3>估算用的是哪一种净值</h3>
    {!ready?<p>基金公司单位净值当前未通过原响应核对，不沿用旧数量或日记录。</p>:<>
      <p>已逐条核对 {data.nav_observations} 条单位净值，绑定 {data.source_response_count} 个原响应引用；窗口 {data.start} 至 {data.through}。累计净值、参考净值和基金资产净值均不作为这里的单位净值。</p>
      <p>净值对应无误只验证这一项输入，不确认基金全量份额、份额精度、最终修订或全窗事件，净申赎金额继续未发布。</p>
      <details className="market-source-notes"><summary>查看基金公司原始单位净值</summary>
        <div className="learning-filters"><label>单位净值来源 <select aria-label="单位净值原响应基金筛选" value={selected} onChange={e=>setSelected(e.target.value)}>{data.funds.map(f=><option key={f.code} value={f.code}>{f.code} · {f.source_field}</option>)}{!fund&&<option value={selected} disabled>{selected||'上次选择'}（当前未取得）</option>}</select></label></div>
        {!fund?<p>当前选择没有已核对的单位净值，不继续展示上次记录。</p>:<>
          {target!==data.through&&<p>本项终点 {data.through} 与市场目标 {target||'未确定'} 不同，不算作目标日覆盖。</p>}
          <p>使用基金公司字段“{fund.source_field}”，单位元/份。<a href={fund.source_url} target="_blank" rel="noreferrer">基金公司净值来源 ↗</a>；绑定 {fund.source_response_count} 个原响应引用。本窗小数文本分布：{Object.entries(fund.fractional_digit_counts).map(([n,count])=>`${n}位 ${count}条`).join('；')}；不把小数位当成份额字段的精度。</p>
          <details><summary>查看该基金全部来源依据（{fund.source_responses.length}项）</summary>{fund.source_responses.map((ref,i)=><p key={i}>{ref.role==='product_identity'?'产品身份':ref.role==='unit_NAV_schema'?'单位净值字段对应':'单位净值数据'} · <a href={ref.method==='POST'?fund.source_url:ref.url+(Object.keys(ref.params).length?'?'+new URLSearchParams(Object.entries(ref.params).map(([k,v])=>[k,String(v)])).toString():'')} target="_blank" rel="noreferrer">{ref.method==='POST'?'查询页':'原链接'} {i+1} ↗</a>；取得 {time(ref.observed_at)}（北京时间）<small>原响应摘要 <code>{ref.response_sha256}</code></small></p>)}</details>
          <p>表格可左右滑动、向下查看其余日期；聚焦表格后可用方向键及翻页键滚动。原响应按首次取得时间保留，不回填为历史当时可见。</p>
          {fund.records.length===0?<p>本基金无已核对日记录，缺失不填零。</p>:<div className="learning-table-wrap market-notice-clauses" role="region" aria-label="可滚动的原始单位净值表" tabIndex={0} onKeyDown={scrollTable}><table className="learning-table market-nav-source-table"><colgroup><col style={{width:'22%'}}/><col style={{width:'25%'}}/><col style={{width:'28%'}}/><col style={{width:'25%'}}/></colgroup><thead><tr><th scope="col">净值所属日期</th><th scope="col">单位净值（元/份）</th><th scope="col">原响应与取得时间</th><th scope="col">来源对应依据</th></tr></thead><tbody>{fund.records.map(row=><tr key={row.date}>
            <th scope="row">{row.date}</th><td>{row.raw_text}<small>原始小数文本</small></td><td><a href={row.request_method==='GET'?row.source_url:fund.source_url} target="_blank" rel="noreferrer">{row.request_method==='GET'?'原响应入口 ↗':'基金公司查询页 ↗'}</a><small>{time(row.observed_at)}（北京时间）</small></td><td><details><summary>查看本条来源对应</summary><p>原字段 {fund.source_field}；{row.request_method==='POST'?'原响应来自查询提交；此链接打开查询页，不重放提交。':'原链接保留实际查询参数。'}</p><code>{row.response_sha256}</code></details></td>
          </tr>)}</tbody></table></div>}
          <p>当前显示 {fund.records.length} 条；快照 <code>{data.snapshot_digest}</code></p>
        </>}
        <p>{data.note}</p>
      </details>
    </>}
  </div>
}
