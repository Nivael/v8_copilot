import {useState} from 'react'
import type {ETFReviewScope as Review} from './types'
import {formatShareCount as shares} from './numbers'

const time=(value:string|undefined)=>value?new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未取得'

export function ETFReviewScope({data}:{data:Review}){
  const [code,setCode]=useState('all')
  const [scope,setScope]=useState('all')
  const [kind,setKind]=useState('creation_unit_declaration')
  const ready=data.availability==='scoped_reviewed'&&data.all_selected_items_have_scoped_review
    &&data.documents.length>0&&data.documents.length===data.selected_document_items
    &&data.items_with_scoped_review===data.selected_document_items&&data.items_without_scoped_review===0
  const labels=data.scope_labels||{}
  const codes=[...new Set(data.documents.map(row=>row.code))].sort()
  const shown=data.documents.filter(row=>(code==='all'||row.code===code)&&(scope==='all'||row.review_scopes.includes(scope)))
  const supplements=data.supplemental_documents.filter(row=>kind==='all'||row.kind===kind)
  return <section className="learning-freshness" aria-label="ETF文档指定范围汇总">
    <header className="learning-section-head"><div><p className="eyebrow">原文依据 / 核对范围</p><h2>每份文档核对了什么</h2></div><span>{ready?`${data.items_with_scoped_review}/${data.selected_document_items} 项有指定范围依据`:'汇总尚未通过当前来源校验'}</span></header>
    {!ready?<p>暂不展示上次的覆盖数量或条款。公告目录、文本提取与全窗事件验收仍分别记录，净申赎金额继续未发布。</p>:<>
      <p>这是 {data.selected_document_items} 个基金文档项的核对范围汇总；同一原件若涉及不同基金，会分别计项。全文语义、全窗份额事件、日份额范围与精度、最新修订仍未验收，净申赎金额继续未发布。</p>
      <p>{Object.entries(data.scope_counts||{}).map(([key,count])=>`${labels[key]||key} ${count} 项`).join('；')}。</p>
      <details className="market-source-notes"><summary>查看全部文档与核对页（{data.selected_document_items}项）</summary>
        <p>{data.pdf_items} 个PDF文档项对应 {data.distinct_pdf_originals} 份不同原PDF，另有 {data.issuer_html_items} 个发行人HTML正文项。PDF页数按基金文档项合计 {data.pdf_pages_by_item} 页，原件去重后 {data.distinct_pdf_pages} 页；页数只说明材料体量，不代表这些页全部完成语义核对。</p>
        <div className="learning-filters">
          <label>ETF <select aria-label="文档范围ETF筛选" value={code} onChange={e=>setCode(e.target.value)}><option value="all">全部ETF</option>{codes.map(value=><option key={value} value={value}>{value}</option>)}{code!=='all'&&!codes.includes(code)&&<option value={code} disabled>{code}（当前未取得）</option>}</select></label>
          <label>核对范围 <select aria-label="文档核对范围筛选" value={scope} onChange={e=>setScope(e.target.value)}><option value="all">全部范围</option>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
          <span aria-live="polite">显示 {shown.length}/{data.selected_document_items} 项</span>
        </div>
        <p>表格可左右滑动，向下滚动查看其余文档。PDF链接指向实际物理页；HTML正文没有PDF页码。</p>
        <div className="learning-table-wrap market-notice-clauses" role="region" aria-label="可滚动的ETF文档范围表" tabIndex={0}><table className="learning-table"><colgroup><col style={{width:'45%'}}/><col style={{width:'25%'}}/><col style={{width:'30%'}}/></colgroup><thead><tr><th scope="col">基金 / 公告</th><th scope="col">已核对的范围</th><th scope="col">原文依据</th></tr></thead><tbody>{shown.map(row=><tr key={row.document_id}>
          <th scope="row">{row.code}<small>{row.published_on} · {row.title}</small><small>{row.review_reason==='historical_share_title'?'观察窗外的历史份额相关标题':'按披露日选入的文档'}</small></th>
          <td>{row.review_scopes.map(key=><p key={key}>{labels[key]||key}</p>)}<small>仅限已列范围</small></td>
          <td>{row.format==='issuer_html'?<a href={row.source_url} target="_blank" rel="noreferrer">发行人HTML正文 ↗</a>:row.reviewed_pages.map(page=><small key={page}><a href={`${row.source_url}#page=${page}`} target="_blank" rel="noreferrer">原PDF第{page}页 ↗</a></small>)}<small>本次取得 {time(row.observed_at)}</small></td>
        </tr>)}</tbody></table></div>
        {shown.length===0&&<p>当前筛选没有文档，可切换ETF或核对范围。</p>}
      </details>
      <details className="market-source-notes"><summary>查看补充的历史业务条款（{data.supplemental_items}项）</summary>
        <p>每笔单位公告 {data.supplemental_counts?.creation_unit_declaration} 项合为 {data.distinct_creation_unit_declarations} 组声明，重复提示 {data.duplicate_unit_reminders} 项不新增事项。另有流动性服务终止 {data.supplemental_counts?.liquidity_service_end} 项、申赎暂停 {data.supplemental_counts?.creation_redemption_pause} 项。它们均在本次公告观察窗外，不证明观察窗内没有其他事件。</p>
        <p>以下日期是公告声明的业务日期，未据此确认实际实施或当前仍有效。每笔最小申赎单位不能作为基金总份额折算倍数；券商流动性服务终止不能解释为基金终止或资金撤退。</p>
        <label>业务条款 <select aria-label="历史业务条款筛选" value={kind} onChange={e=>setKind(e.target.value)}><option value="all">全部补充条款</option>{['creation_unit_declaration','liquidity_service_end','creation_redemption_pause'].map(key=><option key={key} value={key}>{labels[key]||key}</option>)}</select></label>
        <p aria-live="polite">显示 {supplements.length}/{data.supplemental_items} 项补充条款</p>
        <p>表格可左右滑动，向下滚动查看其余条款。</p>
        <div className="learning-table-wrap market-notice-clauses" role="region" aria-label="可滚动的ETF历史业务条款表" tabIndex={0}><table className="learning-table"><colgroup><col style={{width:'28%'}}/><col style={{width:'30%'}}/><col style={{width:'42%'}}/></colgroup><thead><tr><th scope="col">基金 / 公告</th><th scope="col">声明的业务安排</th><th scope="col">原文与日期角色</th></tr></thead><tbody>{supplements.map(row=><tr key={row.document_id}>
          <th scope="row">{row.code}<small>{row.published_on} · {row.title}</small><small>{labels[row.kind]}</small></th>
          <td>{row.kind==='creation_unit_declaration'?<><p>{row.unit_before_shares==null?'原单位未载明':`${shares(row.unit_before_shares)} 份`} → {shares(row.unit_after_shares||'—')} 份</p><small>每笔最小申购、赎回单位</small><small>未知原单位不从其他公告推算</small></>:row.kind==='liquidity_service_end'?<><p>{row.provider}</p><small>终止该券商为本基金提供流动性服务</small></>:<><p>基金主代码 {row.code.slice(0,6)}；申购赎回业务代码 {row.creation_redemption_code}</p><small>暂停申购及赎回，不新增一条折算</small></>}
            <small>公告声明{row.kind==='creation_redemption_pause'?'暂停起始日':'生效日'} {row.announced_effective_on}</small>
            {row.record_on&&<small>权益登记日 {row.record_on}</small>}{row.related_event_date&&<small>关联已核折算日 {row.related_event_date}</small>}{row.announced_resume_on&&<small>公告声明恢复日 {row.announced_resume_on}</small>}
          </td>
          <td>{row.proofs.map((proof,i)=><p key={i}>{proof.text} {row.format==='issuer_html'?<a href={row.source_url} target="_blank" rel="noreferrer">发行人HTML正文 ↗</a>:<a href={`${row.source_url}#page=${proof.page}`} target="_blank" rel="noreferrer">原PDF第{proof.page}页 ↗</a>}</p>)}<small>本次取得 {time(row.observed_at)}</small></td>
        </tr>)}</tbody></table></div>
      </details>
      <details className="market-source-notes"><summary>来源、观察窗与本次核对时间</summary><p>公告检索截至 {data.publication_cutoff} 的采集时点；披露日观察窗 {data.window_start} 至 {data.window_end}。历史份额相关标题另行选入。材料最后取得 {time(data.capture_completed_at)}；本次汇总生成 {time(data.materialized_at)}，均为北京时间。</p><p>{data.note}</p><p>公告目录 <code>{data.catalog_digest}</code></p><p>原文归档 <code>{data.capture_digest}</code></p><p>范围汇总 <code>{data.content_digest}</code></p></details>
    </>}
  </section>
}
