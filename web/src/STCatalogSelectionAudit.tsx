import audit from './catalogSelectionAudit.json'
import type {STRegimeData} from './stRegimeTypes'
export function catalogCaseBound(context:unknown,symbol:string){
 const review=audit.review_outcomes.find(r=>r.symbol===symbol)
 if(!review)return false
 const d=context as {sources?:Record<string,unknown>[];chains?:Record<string,unknown>[]} | null | undefined
 const source=d?.sources?.find(s=>s.announcement_id===review.expected_source.announcement_id)
 const chain=d?.chains?.find(c=>c.chain===review.expected_chain.chain)
 return Boolean(source&&chain&&Object.entries(review.expected_source).every(([k,v])=>source[k]===v)&&Object.entries(review.expected_chain).every(([k,v])=>JSON.stringify(chain[k])===JSON.stringify(v)))
}
export function STCatalogCaseUpdate({symbol,context}:{symbol:string;context:unknown}){
 const review=audit.review_outcomes.find(r=>r.symbol===symbol)
 if(!review)return null
 if(!catalogCaseBound(context,symbol))return <p role="status">目录补核尚未与本案例来源对应，暂不显示新解释。</p>
 return <aside className="regime-boundary" aria-label={`${symbol}目录正文补核`}>
  <h5>{review.title}</h5><p><strong>{review.outcome}。</strong>{review.fact}</p>
  <details><summary>这份补核怎样更新判断？</summary><p>{review.meaning}</p><p>接下来：{review.watch}</p>
   <p>事实以该公司公告披露时为准；这是公司披露，不是另取法院原文或独立银行收款核验。该文件{review.source.pages}页均已看图。</p>
   {Array.from({length:review.source.pages},(_,i)=><p key={i}><a href={`${review.source.url}#page=${i+1}`} target="_blank" rel="noreferrer">{review.source.announcement_id} · 物理第{i+1}页 ↗</a></p>)}
   <p>披露{review.source.published_on} · 保存SHA256：<code>{review.source.sha256}</code>。</p>
   <p>本轮补核不改变下方原行情窗口，也不把附件或原件补强增加为新的独立经验验证。</p>
  </details>
 </aside>
}
export function STCatalogSelectionAudit({data}:{data:STRegimeData}){
 if(data.content_digest!==audit.baseline_snapshot_digest)return <p role="status">目录选源核对对应旧基准，当前输入变化后需重新核对，暂不显示旧统计。</p>
 const c=audit.counts
 return <section aria-label="保存目录与选源完整性核对" className="regime-topic-body">
  <h3>公告已经列在目录里，是否都选进了研究？</h3>
  <p><strong>还不能这样认为。</strong>百利收款公告的遗漏促成本轮核对：检查{c.symbols_with_complete_saved_queries}家公司的{c.capture_pages}页保存目录，共{c.unique_catalog_announcements}条去重记录；按本轮标题规则找到{c.unselected_title_leads}条未进入原选源的线索。正文已核3条：美克补事项链，喜临门补主体区别，中路增强原件依据且原判断保留。</p>
  <p>其余5条仍待核，其中2条公司公告、3条配套材料。标题命中不等于已确认遗漏或新事实，未命中也不证明没有遗漏。固定150家中另66家尚未纳入这批保存目录核对，继续保留范围缺口。</p>
  <p><a href="/runs#research-RUN-83C04A08D7CE4577B6CB4B3C">查看本轮目录核对与正文研究 →</a></p>
  <details><summary>已核三条：分别改变了什么？</summary>{audit.review_outcomes.map(r=><STCatalogCaseUpdate key={r.symbol} symbol={r.symbol} context={data.themes?.[r.source_theme as keyof NonNullable<STRegimeData['themes']>]}/>)}</details>
  <details><summary>查看8条原始线索及当前处理状态</summary><div className="regime-scroll"><table className="regime-table"><caption>选源核对线索，不是8个独立新事件</caption><thead><tr><th scope="col">主体与披露日</th><th scope="col">目录标题</th><th scope="col">处理状态</th></tr></thead><tbody>{audit.candidates.map(r=>{
   const reviewed=audit.review_outcomes.find(x=>x.announcement_id===r.announcement_id)
   return <tr key={r.announcement_id}><th scope="row">{r.symbol} {r.name}<small>{r.published_on}</small></th><td>{r.title}<small>{r.announcement_id}</small></td><td>{reviewed?reviewed.outcome:r.supporting_document_title?'配套材料标题线索，正文待核':'公司公告标题线索，正文待核'}</td></tr>
  })}</tbody></table></div><p>配套材料包含说明会、核查意见、自查报告，不直接计作新增独立案例。未核条目没有因标题被填成“已终止”“已收款”或“风险解除”。</p></details>
  <details><summary>核对范围、方法与旧材料清单的区别</summary><p>分页核对采用保存页连续、公司代码一致、记录总数及唯一公告ID一致、终页hasMore=false等条件；只认证这些保存查询分页完整，不认证其查询过滤器覆盖所有公告或最早公开时刻。原始totalpages字段在部分两页查询中为1、单页中为0，未直接拿它当页数。</p><p>已选源判定要求公告ID与文件摘要的来源身份，不等于全文已读。标题筛查只是可重复的有限规则；本轮13条标题命中中，原选源未含8条。新增3份共8页全部看图，通过保护检查；原材料清单1296文件是另一份冻结核账基准，不随本轮自动增加或冒充全知识库统计。</p><p>核对结束：{audit.review_completed_on}。原选源身份数{audit.selected_source_identity_count}，核对基准<code>{audit.baseline_snapshot_digest}</code>。逐查询分页及保存摘要见同版本留档，证据摘要<code>{audit.evidence_sha256}</code>。</p></details>
 </section>
}
