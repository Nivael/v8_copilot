import packet from './cashPlanFollowup.json'
import queue from './catalogFullCoverage.json'
import type {STRegimeData} from './stRegimeTypes'
export function cashPlanBound(data:STRegimeData){return data.content_digest===packet.baseline_snapshot_digest&&packet.prior_queue_evidence_sha256===queue.evidence_sha256}
export const cashPlanReviewedIds=packet.reviewed_ids
export function STCashPlanFollowup({data,symbol}:{data:STRegimeData;symbol?:string}){
 if(!cashPlanBound(data))return null
 const rows=packet.rows.filter(r=>!symbol||r.symbol===symbol)
 if(!rows.length)return null
 return <aside aria-label="赠款与重整计划后续正文补核" className="regime-boundary"><h4>后续正文怎样更新原判断？</h4>{rows.map(r=><article key={r.announcement_id}><h5>{r.title}</h5><p>{r.fact}</p><p>{r.change}</p><details><summary>哪些仍未完成 · {r.symbol}</summary><p>{r.limit}</p><p>下一步：{r.watch}</p><p>本件{r.source.pages}物理页均已看图；公司披露日期、落款和收到/截至日期分别保留。</p>{r.visual_pages.map(page=><p key={page}><a href={r.source.url+'#page='+page} target="_blank" rel="noreferrer">{r.announcement_id} · 原件物理第{page}页 ↗</a></p>)}<p>文件SHA256：<code>{r.source.sha256}</code>。</p></details></article>)}<p>原行情与原判断保留各自日期；本次补核尚未新增同窗收益，也不增加独立经验验证。</p><p><a href={'/runs#research-'+packet.research_run_id}>查看赠款与计划批准补核研究 →</a></p></aside>
}
