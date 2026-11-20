import packet from './subsidiaryExitFollowup.json'
import cash from './cashPlanFollowup.json'
import queue from './catalogFullCoverage.json'
import type {STRegimeData} from './stRegimeTypes'
export function subsidiaryExitBound(data:STRegimeData){return data.content_digest===packet.baseline_snapshot_digest&&packet.prior_cash_plan_evidence_sha256===cash.evidence_sha256&&packet.queue_evidence_sha256===queue.evidence_sha256}
export const subsidiaryExitReviewedIds=packet.reviewed_ids
export function STSubsidiaryExitFollowup({data,symbol}:{data:STRegimeData;symbol?:string}){
 if(!subsidiaryExitBound(data))return null
 const rows=packet.reviews.filter(r=>!symbol||r.symbol===symbol)
 if(!rows.length)return null
 const sourceIds=new Set(rows.flatMap(r=>r.source_ids))
 const sources=packet.sources.filter(s=>sourceIds.has(s.announcement_id))
 const pages=sources.reduce((n,s)=>n+s.pages,0)
 const visual=sources.reduce((n,s)=>n+s.visual_pages.length,0)
 return <details><summary>{symbol?'本公司事项的后续正文补核':'子公司、退出与投资终止：7份正文分别说明什么？'}</summary><p>以下按{rows.length}个问题阅读，保留各公告当时的状态；{sources.length}份文件不当作同等数量的独立案例。{pages}物理页中核看{visual}关键图像页，未将提取文本当全文逐页阅读。</p>{rows.map(r=><article key={r.key}><h4>{r.symbol} · {r.title}</h4><p>{r.fact}</p><p>{r.meaning}</p><details><summary>限制、下一步与原件 · {r.symbol}</summary><p>{r.limits}</p><p>下一步：{r.next}</p>{r.source_ids.map(id=>{const s=packet.sources.find(source=>source.announcement_id===id)!;return <div key={id}><p>{s.published_on} · {s.title} · 共{s.pages}物理页，关键图像页{s.visual_pages.join('、')}。</p>{s.visual_pages.map(page=><p key={page}><a href={s.url+'#page='+page} target="_blank" rel="noreferrer">{id} · 物理第{page}页 ↗</a></p>)}<p>SHA256：<code>{s.sha256}</code>。</p></div>})}</details></article>)}<p>这些补核未新增同窗收益，也不改变既有行情、退出结果或独立经验验证次数。本组保留当时正文口径；两份会计师专项材料的后续补核与原文冲突另列。</p><p><a href={'/runs#research-'+packet.research_run_id}>查看主体、退出与投资终止补核研究 →</a></p></details>
}
