import packet from './catalogResolutionAudit.json'
import queue from './catalogFullCoverage.json'
import companion from './qihuanRepaymentCompanion.json'
import type {STRegimeData} from './stRegimeTypes'
export function STCatalogResolutionAudit({data}:{data:STRegimeData}){
 if(data.content_digest!==packet.baseline_snapshot_digest||packet.prior_11_queue_evidence_sha256!==queue.evidence_sha256||packet.companion_evidence_sha256!==companion.evidence_sha256)return null
 const r=packet.result
 return <details><summary>补上“占款解决完毕”规则后，还有新漏选标题吗？</summary><p>本轮没有发现新的未选标题。保留原规则，新增“资金占用……解决完毕／整改完成”等表述后，完整重放150家253页保存目录；新增命中{r.new_title_matches.length}条，就是已做配套正文补核的启环公告。</p><p>原11条队列继续保留；新版只追加标题匹配记录，不增加独立案例或验证次数。零个新未选命中，不等于所有公告已读或零遗漏。</p><details><summary>查看新旧规则差集、范围与来源</summary><p>旧规则在当前已选源身份下命中{r.base_counts.matched_titles}条、未选0条；扩展新增{r.new_title_matches.length}条、其中未选{r.new_unselected_title_leads.length}条。已选源身份只是文件身份，不自动认证正文已读。</p>{r.new_title_matches.map(m=><p key={m.announcement_id}>{m.symbol} · {m.published_on} · <a href={m.url} target="_blank" rel="noreferrer">{m.title} ↗</a> · {m.announcement_id}。本条正文状态见启环配套补核。</p>)}<p>144家查询从7月4日、6家从7月1日起，均到11月19日；5593条去重ID为混合起点记录数，不是统一窗口公告总数。其他标题表达、其他渠道及未审正文仍有缺口。标题命中不认定偿还事实、遗漏或独立事件。</p><p>本版表达式：<code>{r.rule}</code>。逐页核原字节摘要、身份和完整分页；无新增目录请求。证据摘要<code>{packet.evidence_sha256}</code>。</p><a href={'/runs#research-'+packet.research_run_id}>查看解决类标题规则重放研究 →</a></details></details>
}
