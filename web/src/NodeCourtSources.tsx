import type {NodeCourtSourcePool} from './types'
import {scrollTable} from './tableScroll'

const stages:Record<string,string>={formal_restructuring_accepted:'法院受理重整',restructuring_plan_approved:'法院批准计划'}
const time=(value:string)=>new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})

export function NodeCourtSources({data}:{data?:NodeCourtSourcePool|null}){
  if(!data)return null
  const ready=data.version==='node_public_court_pool_v1'&&data.availability==='observed'&&data.facts.length===data.primary_bound_clauses
  return <details className="market-source-notes" aria-label="新增公开法院条款来源"><summary>查看新增公开法院条款与原件</summary>
    {!ready?<p>新公开法院条款当前未通过来源核对，不沿用旧条款或旧覆盖计数。</p>:<>
      <p>{data.primary_bound_clauses} 份公告、{data.companies} 家公司的法院阶段条款已绑定独立原件。它们与原P6事实链分别计数，没有把原标题记录改成正文事实，也不声称新原件就是原AN标识的同一附件。</p>
      <p>固定框架选定 {data.selected_candidates} 条候选，{data.selected_rejections} 条旧事项回述排除；另核 {data.extra_related_entity_exclusions} 份子公司排除案例。归档共 {data.archived_PDFs} 份PDF、{data.archived_pages} 页，{data.unreviewed_extra_attachments} 份额外相近附件未核本项条款。条款核对不等于全文语义或金标验收。</p>
      <p>裁定日 {data.unknown_decision_dates} 份待核、收到日 {data.unknown_receipt_dates} 份待核，均不以落款或目录日代填。以下披露日只按官方目录北京时间日期使用，不恢复日内发布时间或历史当时可见。来源绑定之后，还需分别核对去重、窗口和数值。</p>
      <p>表格可在自身范围双向滚动；聚焦后可用方向键和翻页键查看。</p>
      <div className="learning-table-wrap market-notice-clauses" role="region" aria-label="可滚动的新增法院条款表" tabIndex={0} onKeyDown={scrollTable}>
        <table className="learning-table market-node-court-table"><thead><tr><th scope="col">公司 / 阶段</th><th scope="col">披露 / 裁定 / 收到</th><th scope="col">法院条款原件</th></tr></thead><tbody>{data.facts.map(fact=><tr key={fact.event_id}>
          <th scope="row">{fact.symbol}<small>{fact.subject}</small><small>{stages[fact.event_type]??'待核阶段'}</small></th>
          <td><small>披露（目录日）</small><span>{fact.information_available_date}</span><small>裁定日</small><span>{fact.decision_date??'待核'}</span><small>收到日</small><span>{fact.receipt_date??'待核'}</span></td>
          <td><span>{fact.court}</span><small>案号：{fact.court_case??'待核'}</small><a href={`${fact.source_url}#page=${fact.stage_proof.page}`} target="_blank" rel="noreferrer">法院条款 · PDF第{fact.stage_proof.page}页 ↗</a>
            {fact.reviewed_pages.filter(page=>page!==fact.stage_proof.page).map(page=><small key={page}><a href={`${fact.source_url}#page=${page}`} target="_blank" rel="noreferrer">其他已核条款 · PDF第{page}页 ↗</a></small>)}
            <details><summary>条款与取得时间</summary><p>{fact.stage_proof.text}</p><p>原件共 {fact.source_pages} 页；本次取得 {time(fact.source_observed_at)}（北京时间）。</p><code>{fact.raw_sha256}</code></details>
          </td>
        </tr>)}</tbody></table>
      </div>
      <p>本项核对 {data.reviewed_at?time(data.reviewed_at):'待核'}（北京时间），重读 {data.metadata_responses} 份原目录响应。原文或身份失配后撤下该池，不据此判断大盘风险效果。</p>
    </>}
  </details>
}
