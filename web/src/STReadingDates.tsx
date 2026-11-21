import update from './catalogNov20Fixed.json'
import full from './catalogFullCoverage.json'
export function STReadingDates({snapshot,comparisonThrough,baselineThrough}:{snapshot:string;comparisonThrough?:string;baselineThrough:string}){
 const bound=snapshot===update.baseline_snapshot_digest&&update.full_catalog_evidence_sha256===full.evidence_sha256&&update.body_phases.every(p=>p.catalog_review_sha256===update.catalog_review_sha256)
 return <div aria-label="本页资料日期与覆盖"><p className="reading-caption">原同窗复盘截至{comparisonThrough||baselineThrough}。{bound?`另补11月20日公告目录：${update.reviewed_count}份正文已核，${update.remaining_count}份待核。`:'20日公告补核尚未与当前快照对应。'}各项资料分别保留日期。</p>
  <details><summary>这些截止日期分别指什么？</summary>
   <p>原制度比较窗口截至{baselineThrough}；后续同窗复盘截至{comparisonThrough||baselineThrough}。公司公告披露日、财务报告期、实际登记日和价格观察终点分别列示，不因一份新公告自动延长全部行情。</p>
   {bound&&<><p>11月20日只是固定历史150家公司的一天目录增量：20家公司有41份附件候选，{update.reviewed_count}份正文已核。不是150家公司最新全部事项均已核完，也不是20日法律ST名单。</p><p>新增正文接入的公司问题保留旧判断与旧行情；旧资料数量清单仍是原核账基准，不把这批直接加成“全知识库已读量”。</p><a href="#st-evidence-inventory">查看20日补核、待核队列与原件 →</a></>}
   <p>市场指数、广度和限价另有各自覆盖：<a href="/market">查看市场判断中的日期与缺口 →</a>。资料核对时间也不等于当时公开时间或当时已经可得。</p>
  </details>
 </div>
}
