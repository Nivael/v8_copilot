import type {ETFRegistrationRules as Rules} from './types'
import {scrollTable} from './tableScroll'

const time=(s:string|undefined)=>s?new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未取得'

export function ETFRegistrationRules({data}:{data:Rules}){
  const ready=data.version==='etf_registration_scoped_rules_v1'&&data.availability==='scoped_rules_reviewed'&&data.reviewed_versions===3&&data.reviewed_clauses===12
    &&new Set(data.documents.map(d=>d.label)).size===3&&['sh-guide','sz-guide','central-exchange'].every(id=>data.documents.some(d=>d.label===id))
  const effective=(label:string)=>data.documents.find(d=>d.label===label)?.effective_on||'未核对'
  return <details className="market-source-notes" aria-label="登记机构规则与日数据范围"><summary>登记机构的规则说明了哪些数据</summary>
    {!ready?<p>登记机构原件条款当前不可用，不沿用上次的具体范围、时点或版本数量。</p>:<>
      <p>已核对目录列示的3份2026版文件、12处指定条款，原PDF合计 {data.source_pages} 页。实际日登记数据待取得。</p>
      <p>本项核对机构数据通道规则。深市和中央平台的施行日分别为 {effective('sz-guide')}、{effective('central-exchange')}；此前版本待核对。</p>
      <p>表格可左右滑动及上下滚动；聚焦后可用方向键、翻页键查看全部三项。</p>
      <div className="learning-table-wrap market-notice-clauses" role="region" aria-label="可滚动的登记机构规则范围表" tabIndex={0} onKeyDown={scrollTable}><table className="learning-table market-registration-table"><thead><tr><th scope="col">文件与版本</th><th scope="col">目录发布 / 文内施行</th><th scope="col">核对范围与原文物理页</th></tr></thead><tbody>{data.documents.map(doc=><tr key={doc.label}>
        <th scope="row">{doc.title}<small>仅 {doc.clause_count} 处指定条款</small><a href={`${doc.response_url}#page=1`} target="_blank" rel="noreferrer">原PDF身份页 ↗</a></th>
        <td>发布 {doc.published_on}<br/>施行 {doc.effective_on}<small><a href={`${doc.response_url}#page=${doc.effective_proof_page}`} target="_blank" rel="noreferrer">施行依据 · 第{doc.effective_proof_page}页 ↗</a></small></td>
        <td>{doc.label==='sh-guide'?<><p>闭市后通过PROP向基金管理人发送全体场内持有人名册。条款范围为场内持有人名册。</p><a href={`${doc.response_url}#page=17`} target="_blank" rel="noreferrer">名册范围 · 第17页 ↗</a></>:doc.label==='sz-guide'?<><p>基金管理人可从D-COM取得每日持有明细（GLRMX.DBF），相关数据由机构直接交换。</p><a href={`${doc.response_url}#page=33`} target="_blank" rel="noreferrer">每日明细 · 第33页 ↗</a><p>场外组合证券申赎指特定直销申报通道。</p><a href={`${doc.response_url}#page=11`} target="_blank" rel="noreferrer">申报通道 · 第11页 ↗</a></>:<><p>此指引不适用于ETF等产品的交易所场内份额业务。参与方须完成平台接入手续；每日备份是增量，全量备份原则上每年不少于两次。</p><a href={`${doc.response_url}#page=18`} target="_blank" rel="noreferrer">适用排除 · 第18页 ↗</a><p>该平台备份及格式错误补正时点为T+1日21:00。</p><a href={`${doc.response_url}#page=9`} target="_blank" rel="noreferrer">增量与格式补正 · 第9页 ↗</a></>}</td>
      </tr>)}</tbody></table></div>
      <p>这里只核对所列制度条款；未证明8只基金已实际使用某一业务、全基金日份额齐全或资金身份，净申赎金额继续未发布。</p>
      <details><summary>查看全部指定证明页与取得时间</summary>{data.documents.map(doc=><div key={doc.label}><p>{doc.title}；原件取得 {time(doc.observed_at)}（北京时间）。</p><p>{doc.proof_pages.map(page=><a key={page} href={`${doc.response_url}#page=${page}`} target="_blank" rel="noreferrer">第{page}物理页 ↗ </a>)}</p><p>原PDF <code>{doc.raw_sha256}</code></p></div>)}</details>
      <p>目录读取 {time(data.index?.observed_at)}；本次离线核对生成 {time(data.materialized_at)}（北京时间），不回填为历史当时可见。</p><p>{data.note}</p><p>本次核对 <code>{data.content_digest}</code></p>
    </>}
  </details>
}
