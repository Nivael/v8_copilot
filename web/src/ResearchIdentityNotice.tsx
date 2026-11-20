import {useEffect,useState} from 'react'
import {Link} from 'react-router-dom'
import {getResearchIdentityNotes} from './api'
export type ResearchIdentityNote={run_id:string;corrected_question:string;corrected_object_refs:string[];corrected_research_as_of:string;original_question:string;original_object_refs:string[];original_research_as_of:string|null;reviewed_at:string;experience_context:'inherited_unreviewed';topic_changed:boolean}
export function ResearchIdentityNotice({note}:{note:ResearchIdentityNote}){
 return <aside aria-label="研究登记身份更正"><p><strong>登记身份已校正，原记录保留。</strong> 阅读主题以本次校正为准；原回答与证据包未改写。这不是恢复或改写用户原始问句。</p><p>研究对象：{note.corrected_object_refs.join('、')}；本轮资料截止：{note.corrected_research_as_of}。各原件日期仍分别保留。</p><p>原经验命中属于未复核的继承检索背景，不认证本轮实际使用、独立复现或效果提升。</p><details><summary>查看原始登记身份</summary><p>原登记题目：{note.original_question}</p><p>原对象：{note.original_object_refs.join('、')}；原证据包截止：{note.original_research_as_of||'未填'}。</p><p>校正记录时间：{new Date(note.reviewed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}（北京时间）</p></details></aside>
}
export function ResearchIdentitySummary(){
 const [notes,setNotes]=useState<ResearchIdentityNote[]|null>(null);const [error,setError]=useState(false)
 useEffect(()=>{const c=new AbortController();getResearchIdentityNotes(c.signal).then(setNotes).catch(()=>{if(!c.signal.aborted)setError(true)});return()=>c.abort()},[])
 if(error)return <p role="status">研究登记身份核对暂不可读，<Link to="/runs">查看原运行记录</Link>；未将缺失视为已审无误。</p>
 if(!notes?.length)return null
 return <section aria-label="近期研究登记更正"><p>{notes.length}条近期复盘的登记身份已校正，原登记、原答和原证据包保留。<Link to="/runs">查看更正与原记录 →</Link></p><details><summary>哪些主题和日期经过校正？</summary><ul>{notes.map(n=><li key={n.run_id}><Link to={'/runs#research-'+n.run_id}>{n.corrected_question}</Link> · 资料截止{n.corrected_research_as_of}{n.topic_changed?' · 主题与对象已校正':' · 原主题保留，仅校正日期与上下文标记'}</li>)}</ul><p>这不是新增研究或经验验证；其他历史记录未因此获得身份审计认证。</p></details></section>
}
