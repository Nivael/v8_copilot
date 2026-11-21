import packet from './judicialNov20CaseLinks.json'
import catalog from './catalogNov20Fixed.json'
function matches(expected:unknown,actual:unknown):boolean{
 if(Array.isArray(expected))return Array.isArray(actual)&&expected.length===actual.length&&expected.every((v,i)=>matches(v,actual[i]))
 if(expected!==null&&typeof expected==='object')return actual!==null&&typeof actual==='object'&&Object.entries(expected).every(([k,v])=>matches(v,(actual as Record<string,unknown>)[k]))
 return expected===actual
}
export function judicialNov20CaseBound(code:string,context:unknown){
 const link=packet.links.find(l=>l.code===code)
 const c=context as {through?:string;sources?:{symbol:string}[];chains?:{chain:string}[]}|undefined
 if(!link||!c?.sources||!c.chains)return false
 const selected={through:c.through,sources:c.sources.filter(s=>s.symbol===code),chains:c.chains.filter(s=>s.chain.startsWith(code+'-'))}
 const finding=catalog.findings.find(f=>f.announcement_id===link.finding.announcement_id)
 return matches(link.expected_context,selected)&&catalog.body_phases.some(p=>p.sha256===packet.judicial_review_sha256)&&matches(link.finding,finding)&&matches(link.source,finding?.source)
}
export function STJudicialNov20CaseUpdate({code,context}:{code:string;context:unknown}){
 const link=packet.links.find(l=>l.code===code)
 if(!link)return null
 if(!judicialNov20CaseBound(code,context))return <p role="status">20日司法补核与原公司事项链未对应，暂不接入新解释。</p>
 return <aside className="regime-boundary" aria-label={`${code}20日事项链更新`}><h4>{link.reading.title}</h4><p><strong>{link.reading.meaning}</strong></p><p>{link.reading.watch}</p>
 <details><summary>新公告怎样接回原问题？</summary><p>{link.finding.answer}</p><p>{link.finding.boundary}</p>{link.finding.pages.map(page=><p key={page}><a href={link.source.url+'#page='+page} target="_blank" rel="noreferrer">20日公告 · 物理第{page}页 ↗</a></p>)}<p>原事项链截至{link.expected_context.through}，新事项披露20日；原文字与行情窗口保留，未新增同窗收益或独立验证。全文已提取，关键图像核看{link.source.visual_physical_pages.join('、')}页，未独立取得法院原文。</p><p>更新摘要：<code style={{overflowWrap:'anywhere'}}>{packet.evidence_sha256}</code>。</p></details></aside>
}
