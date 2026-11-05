import {useState} from 'react'
import type {ETFNoticeReview as Review} from './types'
import {formatShareCount as exact} from './numbers'

const categories:Record<string,string>={portfolio_allocation:'持仓证券获配',private_placement:'持仓股票定向认购',listing_valuation_risk:'新股上市估值提示',creation_redemption_agent:'新增申赎代办机构',liquidity_provider:'流动性服务商安排'}

export function ETFNoticeReview({data}:{data:Review}){
  const [code,setCode]=useState('all')
  const [category,setCategory]=useState('all')
  const codes=[...new Set(data.notices.map(row=>row.code))].sort()
  const shown=data.notices.filter(row=>(code==='all'||row.code===code)&&(category==='all'||row.category===category))
  return <section className="learning-freshness" aria-label="ETF公告正文事项核对">
    <header className="learning-section-head"><div><p className="eyebrow">公告正文 / 单位与口径</p><h2>持仓、估值与服务安排</h2></div><span>已核对正文事项 {data.reviewed_notices} 条</span></header>
    <p>{data.note}</p>
    {data.catalog_window_start&&data.catalog_window_end&&<p>公告筛选窗 {data.catalog_window_start} 至 {data.catalog_window_end}，按披露日筛选；与主图的近两个月市场窗口分开。披露日不等于证券获配日期，首次取得时间也不回填为当时已知。</p>}
    {data.notices.length===0?<p>所列正文事项尚未通过当前原文核对，暂不展示已失效的分类或金额。</p>:<>
      <p>持仓获配或认购 {(data.category_counts.portfolio_allocation||0)+(data.category_counts.private_placement||0)} 条；新股估值提示 {data.category_counts.listing_valuation_risk||0} 条；申赎代办机构 {data.category_counts.creation_redemption_agent||0} 条；流动性服务商 {data.category_counts.liquidity_provider||0} 条。</p>
      <p>覆盖 {data.reviewed_funds} 只ETF，按基金目录条目计 {data.reviewed_notices} 条，对应 {data.distinct_original_pdfs} 份不同PDF。公告筛选窗内其余 {data.window_documents_outside_this_review??'—'}/{data.window_selected_documents??'—'} 份尚未做本项正文核对，包含定期报告及招募说明书；定期报告份额表、招募规则另列。</p>
      <p>发现 {data.repeat_disclosure_groups.length} 组同一基金与证券的获配数量、金额重复披露，分开回链，不累计成新增申赎。股、张均属于持仓证券，不是ETF份额。</p>
      <details className="market-source-notes"><summary>查看正文核对（{data.reviewed_notices}条）</summary>
        <div className="learning-filters">
          <label>ETF <select aria-label="正文ETF筛选" value={code} onChange={event=>setCode(event.target.value)}><option value="all">全部ETF</option>{codes.map(value=><option key={value} value={value}>{value}</option>)}{code!=='all'&&!codes.includes(code)&&<option value={code} disabled>{code}（当前未取得）</option>}</select></label>
          <label>事项 <select aria-label="正文类型筛选" value={category} onChange={event=>setCategory(event.target.value)}><option value="all">全部类型</option>{Object.entries(categories).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
          <span>当前显示 {shown.length}/{data.notices.length} 条；整体核对数量不随筛选改变</span>
        </div>
        {shown.length===0?<p>当前筛选没有通过原文核对的事项，可切换ETF或类型查看。</p>:<div className="learning-table-wrap"><table className="learning-table market-notice-table"><thead><tr><th scope="col">ETF / 公告与原文</th><th scope="col">正文事项</th><th scope="col">持仓证券数值 / 服务安排</th><th scope="col">日期、重复披露与范围</th></tr></thead><tbody>{shown.map(row=>{
          const repeats=data.repeat_disclosure_groups.filter(group=>group.document_ids.includes(row.document_id))
          return <tr key={row.document_id}>
            <th scope="row">{row.code}<small>披露于 {row.published_on}</small><small>{row.title}</small>{row.evidence_pages.map(page=><small key={page}><a href={`${row.url}#page=${page}`} target="_blank" rel="noreferrer">正文或表格 · PDF第{page}页 ↗</a></small>)}</th>
            <td>{categories[row.category]||'范围待核对'}<small>不计作ETF份额申赎</small>{row.risk_clause&&<details><summary>IOPV与净值差异原文</summary><p>{row.risk_clause}</p></details>}</td>
            <td>{row.allocations.map(item=><div key={item.issuer}><p>{item.issuer}：{exact(item.quantity)} {item.asset_unit==='bond_piece'?'张（可转债）':'股（持仓证券）'}；{row.category==='private_placement'?'认购成本':'获配金额'} {exact(item.amount_yuan)} 元。</p></div>)}
              {row.service&&<><p>{row.service.provider}</p><small>公告角色：{row.service.role}</small><small>公告生效日 {row.service.effective_on}</small></>}
              {row.reported_weight_text&&<><small>披露占比 {row.reported_weight_text}（两位小数）</small>{row.reported_weight_text==='0.00%'&&<small>显示0.00%不代表零持仓</small>}</>}
            </td>
            <td>{row.listing_on&&<><small>公告挂牌日 {row.listing_on}</small><small>占比分母净值日期 {row.nav_reference_on}</small></>}
              {row.reference_description&&!row.listing_on&&<small>{row.reference_description}</small>}
              {repeats.map(group=><div key={group.issuer}><small>{group.issuer}另有相同获配披露，未累计金额：</small>{group.document_ids.filter(id=>id!==row.document_id).map(id=>{const peer=data.notices.find(item=>item.document_id===id);return peer&&<small key={id}><a href={`${peer.url}#page=${peer.allocations.find(item=>item.issuer===group.issuer)?.table_page||1}`} target="_blank" rel="noreferrer">{peer.published_on} · 对应披露 ↗</a></small>})}</div>)}
              <small>本次取得 {new Date(row.observed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}（北京时间）</small>
              <small>仅核对所列事实，不代表全文或观察窗核验完成</small>
            </td>
          </tr>
        })}</tbody></table></div>}
      </details>
    </>}
  </section>
}
