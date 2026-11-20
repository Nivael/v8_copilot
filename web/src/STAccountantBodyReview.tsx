import packet from './accountantBodyReview.json'
import prior from './subsidiaryExitFollowup.json'
import type {STRegimeData} from './stRegimeTypes'
export function accountantBodyBound(data:STRegimeData){return data.content_digest===packet.baseline_snapshot_digest&&packet.prior_evidence_sha256===prior.evidence_sha256}
export const accountantReviewedIds=packet.sources.map(s=>s.announcement_id)
export function STAccountantBodyReview({data,symbol}:{data:STRegimeData;symbol?:string}){
 if(!accountantBodyBound(data))return null
 const rows=packet.reviews.filter(r=>!symbol||r.symbol===symbol)
 if(!rows.length)return null
 return <details><summary>会计师材料怎样更新清偿判断？{symbol?' · '+symbol:''}</summary>
 <p>正文已核与疑点消除分开记录。西发是历史累计清偿；启环报告称投资人代偿到账，但报告内表述和日期冲突仍待解释。</p>
 {rows.map(r=>{const s=packet.sources.find(s=>s.announcement_id===r.announcement_id)!;return <article key={r.announcement_id}><h4>{r.symbol==='000752'?'西发：清偿总额不等于本期新增现金':'启环：报告称占款已代偿，担保不能一并划掉'}</h4><p>{r.conclusion}</p><p>{r.limits}</p>{r.conflicts&&<aside aria-label="原文冲突仍待解释"><strong>原文冲突仍待解释</strong>{r.conflicts.map(c=><p key={c}>{c}</p>)}</aside>}
 <details><summary>日期、核验范围与原件 · {r.symbol}</summary><p>目录披露{r.catalog_date}；签章{r.signed_date}。{r.symbol==='000752'?'余额截至2025-12-31；16行金额加总92689.94万元核对一致，含现金与债权抵偿。':'报告开头核查截至2026-08-26，后文收款截至2026-08-25；签章2026-08-25，保留日期衔接问题。'}</p><p>共{s.pages}物理页，实际核看关键图像页{s.visual_pages.join('、')}。未将文本提取当全文逐页阅读，西发扫描关键页依原件图像核对。</p>{s.visual_pages.map(page=><p key={page}><a href={s.url+'#page='+page} target="_blank" rel="noreferrer">{s.announcement_id} · 物理第{page}页 ↗</a></p>)}<p>SHA256：<code>{s.sha256}</code>。</p></details></article>})}
 <p>保留8月19日风险披露与8月26日核查报告各自的已知范围，不覆盖旧余额，也不把新报告当新独立案例。本轮未增加收益窗口或独立经验验证。</p><p><a href={'/runs#research-'+packet.research_run_id}>查看会计师清偿补核研究 →</a></p></details>
}
