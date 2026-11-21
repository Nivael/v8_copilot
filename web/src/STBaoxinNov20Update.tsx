import link from './baoxinNov20CaseLink.json'
import catalog from './catalogNov20Fixed.json'
function matches(expected:unknown,actual:unknown):boolean{
 if(Array.isArray(expected))return Array.isArray(actual)&&expected.length===actual.length&&expected.every((v,i)=>matches(v,actual[i]))
 if(expected!==null&&typeof expected==='object')return actual!==null&&typeof actual==='object'&&Object.entries(expected).every(([k,v])=>matches(v,(actual as Record<string,unknown>)[k]))
 return expected===actual
}
export function baoxinNov20Bound(context:unknown){
 const finding=catalog.findings.find(f=>f.announcement_id===link.finding.announcement_id)
 return matches(link.expected_context,context)&&catalog.body_phases.some(p=>p.sha256===link.judicial_review_sha256)&&matches(link.finding,finding)&&matches(link.source,finding?.source)
}
export function STBaoxinNov20Update({context}:{context:unknown}){
 if(!baoxinNov20Bound(context))return <p role="status">20日宝馨补核与原个股来源未对应，暂不接入新解释。</p>
 return <aside aria-label="宝馨20日事项链更新" className="regime-boundary"><h4>{link.reading.title}</h4><p><strong>{link.reading.meaning}</strong></p><p>{link.reading.watch}</p>
 <details><summary>这条更新依据什么？</summary><p>{link.finding.answer}</p><p>{link.finding.boundary}</p>{link.finding.pages.map(page=><p key={page}><a href={link.source.url+'#page='+page} target="_blank" rel="noreferrer">20日公告 · 物理第{page}页 ↗</a></p>)}<p>新公告共3页全文提取，关键图像核看1、2页；未另取法院或平台原文。原登记补证截至{link.expected_context.through}，新事项披露20日，日期分开。没有新增同窗收益或独立案例，也不据此判定行情原因。</p><p>补核摘要：<code style={{overflowWrap:'anywhere'}}>{link.evidence_sha256}</code>。</p></details></aside>
}
