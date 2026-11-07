import './researchCorrections.css'

export type ResearchCorrection={old_run_id:string;replacement_run_id:string;original_question_id:string|null;headline:string;summary:string;corrected_at:string}
export type ResearchCorrectionNote=ResearchCorrection&{role:'corrected_study'|'replacement_study'|'original_review'}

export function ResearchCorrectionNotice({note,onOpen,showOriginal=false}:{note:ResearchCorrectionNote;onOpen:(id:string)=>void;showOriginal?:boolean}){
  const date=new Date(note.corrected_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})
  return <section className={`research-correction correction-${note.role}`} aria-label="研究更正">
    <details>
    <summary><span className="correction-kicker">{note.role==='corrected_study'?'这份旧研究有更正':note.role==='replacement_study'?'这是修正后的事实核查':'这条复盘曾作更正'}</span><strong>{note.headline}</strong><span className="correction-expand">展开原因与原文</span></summary>
    <p>{note.summary}</p>
    <div>{note.role!=='replacement_study'&&<button type="button" onClick={()=>onOpen(note.replacement_run_id)}>查看修正后的研究</button>}{note.role!=='corrected_study'&&<button type="button" onClick={()=>onOpen(note.old_run_id)}>查看旧研究原文</button>}{showOriginal&&note.role!=='original_review'&&note.original_question_id&&<button type="button" onClick={()=>onOpen(note.original_question_id!)}>回到当时的原问题</button>}</div>
    <small>更正记录于 {date} · 北京时间</small>
    </details>
  </section>
}
