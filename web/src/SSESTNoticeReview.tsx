import {useState} from 'react'
import type {SSESTNoticeReview as Review} from './types'

const labels:Record<string,string>={warning_added:'已核生效 · 加入',warning_removed:'已核生效 · 移出',application_pending:'撤销申请 · 待审核',
  layered_warning_existing_member:'既有成员 · 叠加警示',existing_warning_described:'既有警示描述或进展'}
const roles:Record<string,string>={effective_date:'实际生效日期',name_direction:'简称变化方向',approval_pending:'审核尚未确定',prior_warning:'原文回述的警示状态',
  layered_warning:'叠加警示描述',continuation_statement:'继续警示描述'}
const time=(value:string|undefined)=>value?new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未取得'

export function SSESTNoticeReview({data}:{data:Review}){
  const [filter,setFilter]=useState('key')
  const ready=data.availability==='reviewed'&&data.review_scope==='security_identity_and_member_status_clauses_only'
    &&data.items.length>0&&data.items.length===data.catalog_items&&data.reviewed_items===data.catalog_items
  const items=data.items.filter(r=>filter==='all'||filter==='key'&&r.kind!=='existing_warning_described'||filter===r.kind)
  return <div aria-label="沪市ST公告成员状态条款核对">
    <h3>从标题筛查补到原文条款</h3>
    {!ready?<p>原文条款核对当前不可用；保留原标题记录，不作已核对处理。</p>:<>
      <p>固定目录 {data.reviewed_items}/{data.catalog_items} 项，涉及 {data.distinct_companies} 家公司、原PDF共 {data.pdf_pages} 页。已逐项核对证券身份和成员状态条款，未声称所有正文语义或逐日法定名单已核验。</p>
      <p>目录检索窗 {data.start} 至 {data.through}；本目录最近公告发布于 {data.latest_publication}。这与上方价格曲线日期分别记录。</p>
      <p>已核生效：加入 {data.counts?.warning_added??0} 项、移出 {data.counts?.warning_removed??0} 项；撤销申请 {data.counts?.application_pending??0} 项、既有成员叠加警示 {data.counts?.layered_warning_existing_member??0} 项、既有警示描述或进展 {data.counts?.existing_warning_described??0} 项。后面三类不据此新增成员调整。</p>
      <label>查看公告 <select aria-label="沪市ST原文条款筛选" value={filter} onChange={e=>setFilter(e.target.value)}><option value="key">生效、申请及叠加事项</option><option value="all">全部目录项</option>{Object.entries(labels).map(([key,label])=><option value={key} key={key}>{label}</option>)}</select></label>
      <p aria-live="polite">显示 {items.length}/{data.catalog_items} 项</p>
      <p>表格可左右滑动查看状态和原文，向下滚动查看其余公告。</p>
      <div className="learning-table-wrap market-notice-clauses" role="region" aria-label="可滚动的沪市ST公告原文条款表" tabIndex={0}><table className="learning-table"><colgroup><col style={{width:'28%'}}/><col style={{width:'24%'}}/><col style={{width:'48%'}}/></colgroup><thead><tr><th scope="col">证券 / 公告发布</th><th scope="col">核对范围内的状态</th><th scope="col">原文条款及实际物理页</th></tr></thead><tbody>{items.map(r=><tr key={r.symbol+r.published_on}>
        <th scope="row">{r.symbol} · {r.name_as_reported}<small>{r.company}</small><small>{r.published_on}</small><small>{r.title}</small><a href={r.catalog_url} target="_blank" rel="noreferrer">原目录标题 ↗</a></th>
        <td>{labels[r.kind]||r.kind}<small>{r.effective_on?`实际生效 ${r.effective_on}`:'本项未登记成员增减生效日'}</small>{r.stated_since_on&&<small>原文回述日期 {r.stated_since_on}</small>}</td>
        <td>{r.proofs.map((p,i)=><p key={i}>{roles[p.role]||p.role}：{p.text} <a href={`${r.source_url}#page=${p.page}`} target="_blank" rel="noreferrer">原PDF第{p.page}页 ↗</a></p>)}<small>原件取得 {time(r.observed_at)}</small></td>
      </tr>)}</tbody></table></div>
      <p>{data.note}</p><p>对应公司目录最后取得 {time(data.metadata_observed_at)}；原PDF最后取得 {time(data.newest_document_observed_at)}；本次核对生成 {time(data.materialized_at)}，均为北京时间。原件取得不回填为历史当时可见。</p>
    </>}
  </div>
}
