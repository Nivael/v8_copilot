import type {NodePublicationMetadata} from './types'
import {scrollTable} from './tableScroll'

export function NodePublicationDates({data}:{data?:NodePublicationMetadata}){
  if(!data)return null
  const ready=data.version==='node_publication_metadata_v1'&&data.availability==='observed'&&data.reviews.length===data.matched_documents
  return <details className="market-source-notes" aria-label="节点官方目录日期核对"><summary>查看官方目录日期与旧字段的对应</summary>
    {!ready?<p>官方目录元数据当前未通过核对，不沿用旧的目录日期或覆盖计数。</p>:<>
      <p>本轮既有事实链的 {data.frame_document_items} 个文档项中，{data.matched_documents} 份匹配官方目录、覆盖 {data.matched_events} 条既有事件；{data.unbound_documents} 个来源标识未匹配，不补作已核。共核对 {data.metadata_responses} 份按公司、日期取得的原响应引用。</p>
      <p>{data.changed_parent_date_documents} 份的旧日期与目录北京时间日期不同。保留旧字段，按原日期、已核落款和官方目录日期中的较晚日期对齐；毫秒字段按北京时间取日期，不当作精确发布时间或历史当时已取得的证明。本项没有新核公告正文，也没有把标题来源改成已核事实。</p>
      <p>表格只在自身范围滚动；聚焦后可用方向键、翻页键查看。附件链接打开对应公告，不重放目录查询。</p>
      <div className="learning-table-wrap market-notice-clauses" role="region" aria-label="可滚动的节点目录日期对照表" tabIndex={0} onKeyDown={scrollTable}><table className="learning-table market-node-publication-table"><thead><tr><th scope="col">对应公告 / 公司</th><th scope="col">旧字段 / 官方目录日期</th><th scope="col">原毫秒值与查询依据</th></tr></thead><tbody>{data.reviews.map(r=><tr key={r.document_id}><th scope="row">{r.symbol}<small>{r.title}</small><a href={r.source_url} target="_blank" rel="noreferrer">对应公告附件 ↗</a></th><td><small>旧字段</small><span>{r.parent_published_dates.join(' / ')}</span><small>目录（北京时间）</small><span>{r.official_catalog_date}</span><small>同值取UTC日期</small><span>{r.utc_interpretation_date}</span></td><td>{r.announcement_time_raw_ms}<small>仅按目录日使用，不恢复日内发布时间</small><details><summary>查询范围、取得时间和原件</summary><p>POST；{r.query_params.stock}；日期范围 {r.query_params.seDate}。</p><p>取得 {new Date(r.observed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}（北京时间）。</p><code>{r.response_sha256}</code></details></td></tr>)}</tbody></table></div>
      <p>目录原件核对标识 <code>{data.profile_digest}</code>。它不证明完整正文语义、历史点时数据或节点/大盘效果。</p>
    </>}
  </details>
}
