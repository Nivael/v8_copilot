import {Fragment} from 'react'
import type {ReactNode} from 'react'
import type {RegimeComparison,STRegimeData} from './stRegimeTypes'
import {buildRegimeStory} from './stRegimeStory'

export function STRegimeArticle({data,comparison,onEvidence,chart}:{data:STRegimeData;comparison:RegimeComparison;onEvidence:(view:string)=>void;chart:ReactNode}){
  const story=buildRegimeStory(data,comparison)
  return <article className="regime-story" aria-label="ST横向研究报道">
    <header className="regime-story-head"><p className="regime-story-rubric">市场观察 <span>ST制度与行情</span></p><h3>{story.title}</h3><p className="regime-story-deck">{story.deck}</p><div className="regime-story-dateline"><span>研究分析 · {story.period}</span><span>{story.coverage}</span></div></header>
    <div className="regime-story-body"><div className="regime-story-lead">{story.lead.map(text=><p key={text}>{text}</p>)}</div>
      {comparison.key==='all'&&<p className="regime-story-note">本篇后窗{comparison.after.days}日，前窗40日，时长不同。展开数据可切换等长20日或40日比较。</p>}
      {story.sections.map((section,index)=><Fragment key={section.id}><section aria-labelledby={`st-story-${section.id}`} className="regime-story-chapter"><h4 id={`st-story-${section.id}`}>{section.heading}</h4>{section.paragraphs.map(text=><p key={text}>{text}</p>)}<div className="regime-story-references"><a href="#st-evidence" onClick={()=>onEvidence(section.evidence)}>核对{section.evidence==='整批个股'?'样本与个股':section.evidence==='大盘联动'?'市场环境对照':'这段行情的数字'} ↓</a>{section.sourceIndices.map(i=>data.sources[i]&&<a key={i} href={data.sources[i].url} target="_blank" rel="noreferrer">{i===0?'上交所说明':i===1?'上交所通知':i===2?'深交所通知':i===3?'逐日名单':i===4?'行情口径':'指数来源'} ↗</a>)}</div></section>{index===0&&chart}</Fragment>)}
      <p className="regime-story-ending">{story.ending}</p>
    </div>
  </article>
}
