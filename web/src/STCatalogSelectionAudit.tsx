import {STCashPlanFollowup,cashPlanBound,cashPlanReviewedIds} from './STCashPlanFollowup'
import audit from './catalogSelectionAudit.json'
import followup from './catalogLeadFollowup.json'
import coverage from './catalogCoverageReuse.json'
import full from './catalogFullCoverage.json'
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
 const followupBound=followup.baseline_snapshot_digest===data.content_digest&&followup.prior_evidence_sha256===audit.evidence_sha256
 const newReviews=followupBound?followup.sources:[]
 const coverageBound=followupBound&&coverage.baseline_snapshot_digest===data.content_digest&&coverage.prior_evidence_sha256===audit.evidence_sha256&&coverage.body_review_sha256===followup.source_review_sha256
 const bodyBound=cashPlanBound(data)
 const fullBound=coverageBound&&full.baseline_snapshot_digest===data.content_digest&&full.prior_90_evidence_sha256===coverage.evidence_sha256
 return <section aria-label="保存目录与选源完整性核对" className="regime-topic-body">
  <h3>公告已经列在目录里，是否都选进了研究？</h3>
  {fullBound&&<><p><strong>固定150家公司均有完整保存查询；{bodyBound?'原11条线索已核2条正文，仍有9条待核。':'原11条线索的后续正文状态待重新绑定。'}</strong>目录覆盖不等于正文已读、所有事项完成或研究无遗漏。本轮补60家公司105页，合计253页保存响应；没有因此增加独立经验验证。</p><details><summary>查看原11条线索：2条已核正文，9条待核</summary><p>涉及5家公司。这里只列目录标题与身份，不把它们当已确认的新事实、研究遗漏或11个独立事件。康佳连续倒计时与说明会可能回指同一退出安排；会计师专项说明、核查报告也不自动当公司公告。</p><div className="regime-scroll"><table className="regime-table"><caption>原11条标题线索及后续正文核对状态</caption><thead><tr><th>公司与目录日</th><th>标题与原件入口</th><th>状态</th></tr></thead><tbody>{full.candidates.map(r=><tr key={r.announcement_id}><th>{r.symbol}<small>{r.published_on}</small></th><td><a href={r.url} target="_blank" rel="noreferrer">{r.title}</a><small>{r.announcement_id}</small></td><td>{bodyBound&&cashPlanReviewedIds.includes(r.announcement_id)?'正文已核，后续执行另看':'标题线索，正文待核'}</td></tr>)}</tbody></table></div></details><details><summary>150家目录覆盖的日期、来源与限制</summary><p>共同目标期间2026-07-04至2026-11-19。原6家查询额外包含7月1—3日，其余144家从7月4日起；保存查询去重{full.counts.unique_catalog_announcements}条是混合起点的记录数，不是统一窗口公告总数。</p><p>全部查询核公司身份、日期参数、原字节摘要和完整分页；没有认证其他渠道、最早公开分钟或所有正文。完整目录核对时，有限标题规则命中25条，其中11条未进入当时已选源集合；后续正文处理状态见上方，不表示规则之外没有缺口。</p><p>原84家、90家阶段及8条旧线索在下方保留。证据摘要：<code>{full.evidence_sha256}</code>。</p><p><a href={'/runs#research-'+full.research_run_id}>查看150家公司目录核对研究 →</a></p></details></>}
  <STCashPlanFollowup data={data}/>
  <details><summary>保留90家覆盖阶段与当时剩余60家</summary>
  {coverageBound&&<><p><strong>当时目录覆盖90／150家公司，仍有60家未纳入完整期间查询核对。</strong>这是目录范围，不是正文已读率。复用本地6家公司10页完整保存响应，并回核原138页，没有新增下载。</p><details><summary>90家覆盖了哪段日期，为什么不是统一窗口公告总数？</summary><p>共同目标期间为{coverage.target_period}。原84家查询从7月4日开始，新增6家从7月1日开始，均到11月19日；新增范围包含更早三天，保存查询去重{coverage.counts.unique_catalog_announcements}条不当作统一日期窗口的公告总数。</p><p>新增公司代码：{coverage.new_symbols.join('、')}。148页原始响应分别与查询参数、文件摘要、连续分页及终页标记核对；只认证这些保存查询，不认证所有渠道的全部公告。</p><p>沿用原有限标题规则，新增6家未出现新未选线索。原8条现均有正文补核，更新已选源集合后未选命中为0，不意味着零遗漏或所有事项已完成。</p><p>尚未纳入的60家公司：{coverage.uncovered_symbols.join('、')}。</p><p>覆盖核对证据摘要：<code>{coverage.evidence_sha256}</code>。原8条线索与原84家范围继续保留在下面。</p><p><a href={'/runs#research-'+coverage.research_run_id}>查看目录覆盖续核研究 →</a></p></details></>}
  </details>
  <details><summary>保留前轮84家目录审查与原8条线索来由</summary>
  <p><strong>还不能这样认为。</strong>百利收款公告的遗漏促成本轮核对：检查{c.symbols_with_complete_saved_queries}家公司的{c.capture_pages}页保存目录，共{c.unique_catalog_announcements}条去重记录；按本轮标题规则找到{c.unselected_title_leads}条未进入原选源的线索。正文已核3条：美克补事项链，喜临门补主体区别，中路增强原件依据且原判断保留。</p>
  <p>{followupBound?'前轮其余5条现已补核正文：2份公司公告、3份配套材料，分别识别募投改投收购、解除受托管理及同事项配套文件。完成正文补核不等于批准、交割或实付完成。':'其余5条的后续补核尚未与当前来源绑定，暂保留前轮待核状态。'}标题命中不等于已确认遗漏或新事实，未命中也不证明没有遗漏。固定150家中另66家尚未纳入这批保存目录核对，继续保留范围缺口。</p>
  </details>
  <p><a href="/runs#research-RUN-83C04A08D7CE4577B6CB4B3C">查看本轮目录核对与正文研究 →</a></p>
  {followupBound&&<details><summary>后续补核五份：哪些不是新的终止事件？</summary>{newReviews.map(r=><article key={r.announcement_id}><h4>{r.symbol} · {r.review_title}</h4><p>{r.reviewed_fact}</p><details><summary>原件与核验范围 · {r.announcement_id}</summary><p>目录披露日{r.published_on}；文件共{r.pages}物理页，全文已提取，关键图像页核看{r.visual_physical_pages.join('、')}。不将全文提取当成全文逐页看图。</p>{r.visual_physical_pages.map(page=><p key={page}><a href={r.url+'#page='+page} target="_blank" rel="noreferrer">原件物理第{page}页 ↗</a></p>)}<p>文件SHA256：<code>{r.sha256}</code>。</p></details></article>)}<p>美克说明会PDF有2物理页且页脚重复1/3，异常保留，不据此补造缺页或认定完整性无疑。本轮5份共{followup.physical_pages}页，核{followup.critical_visual_pages}关键图像页；多份材料不增加独立案例。</p><p><a href={'/runs#research-'+followup.research_run_id}>查看五份正文补核研究 →</a></p></details>}
  <details><summary>已核三条：分别改变了什么？</summary>{audit.review_outcomes.map(r=><STCatalogCaseUpdate key={r.symbol} symbol={r.symbol} context={data.themes?.[r.source_theme as keyof NonNullable<STRegimeData['themes']>]}/>)}</details>
  <details><summary>查看8条原始线索及当前处理状态</summary><div className="regime-scroll"><table className="regime-table"><caption>选源核对线索，不是8个独立新事件</caption><thead><tr><th scope="col">主体与披露日</th><th scope="col">目录标题</th><th scope="col">处理状态</th></tr></thead><tbody>{audit.candidates.map(r=>{
   const reviewed=audit.review_outcomes.find(x=>x.announcement_id===r.announcement_id)
   const newer=newReviews.find(x=>x.announcement_id===r.announcement_id)
   return <tr key={r.announcement_id}><th scope="row">{r.symbol} {r.name}<small>{r.published_on}</small></th><td>{r.title}<small>{r.announcement_id}</small></td><td>{reviewed?reviewed.outcome:newer?'正文已补核：'+newer.review_title:r.supporting_document_title?'配套材料标题线索，正文待核':'公司公告标题线索，正文待核'}</td></tr>
  })}</tbody></table></div><p>配套材料包含说明会、核查意见、自查报告，不直接计作新增独立案例。未核条目没有因标题被填成“已终止”“已收款”或“风险解除”。</p></details>
  <details><summary>核对范围、方法与旧材料清单的区别</summary><p>分页核对采用保存页连续、公司代码一致、记录总数及唯一公告ID一致、终页hasMore=false等条件；只认证这些保存查询分页完整，不认证其查询过滤器覆盖所有公告或最早公开时刻。原始totalpages字段在部分两页查询中为1、单页中为0，未直接拿它当页数。</p><p>已选源判定要求公告ID与文件摘要的来源身份，不等于全文已读。标题筛查只是可重复的有限规则；本轮13条标题命中中，原选源未含8条。新增3份共8页全部看图，通过保护检查；原材料清单1296文件是另一份冻结核账基准，不随本轮自动增加或冒充全知识库统计。</p><p>核对结束：{audit.review_completed_on}。原选源身份数{audit.selected_source_identity_count}，核对基准<code>{audit.baseline_snapshot_digest}</code>。逐查询分页及保存摘要见同版本留档，证据摘要<code>{audit.evidence_sha256}</code>。</p></details>
 </section>
}
