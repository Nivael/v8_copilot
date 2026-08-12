import {BookOpenCheck, Filter, RefreshCw, Sparkles} from 'lucide-react'
import {useCallback, useEffect, useState} from 'react'
import {getExperienceGovernanceStatus, getExperienceReviewQueue, getExperiences, reviewExperience} from './api'
import {ExperienceCard} from './ExperienceCard'
import {ExperienceReviewPanel} from './ExperienceReviewPanel'
import type {Experience, ExperienceGovernanceStatus, ExperienceReviewQueue, ExperienceStatus} from './types'

const FILTERS: Array<{value:ExperienceStatus;label:string}> = [
  {value:'candidate',label:'待审经验'},
  {value:'accepted',label:'已接受'},
  {value:'blocked',label:'需要证据'},
  {value:'ignored',label:'已忽略'},
  {value:'merged',label:'已合并'},
]

export function ExperienceCenter() {
  const [status,setStatus]=useState<ExperienceStatus>('candidate')
  const [experiences,setExperiences]=useState<Experience[]>([])
  const [governance,setGovernance]=useState<ExperienceGovernanceStatus|null>(null)
  const [reviewQueue,setReviewQueue]=useState<ExperienceReviewQueue|null>(null)
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [busyId,setBusyId]=useState('')

  const load=useCallback(async(signal?:AbortSignal)=>{
    setLoading(true)
    setError('')
    try{
      const [rows,governanceStatus,queue]=await Promise.all([
        status==='candidate'?Promise.resolve([]):getExperiences(status,signal),
        getExperienceGovernanceStatus(signal),
        status==='candidate'?getExperienceReviewQueue(signal):Promise.resolve(null),
      ])
      setExperiences(rows);setReviewQueue(queue)
      setGovernance(governanceStatus)
    }
    catch(reason){if(!(reason instanceof DOMException&&reason.name==='AbortError'))setError('经验中心暂时无法读取本地经验库。')}
    finally{if(!signal?.aborted)setLoading(false)}
  },[status])

  useEffect(()=>{
    const controller=new AbortController()
    void load(controller.signal)
    return()=>controller.abort()
  },[load])

  async function onReview(experience:Experience,action:'accept'|'ignore'|'block'|'close'){
    setBusyId(experience.experience_id)
    setError('')
    try{
      await reviewExperience(experience.experience_id,action)
      setExperiences(current=>current.filter(row=>row.experience_id!==experience.experience_id))
    }catch{setError('审阅操作未完成，请保留候选并重试。')}
    finally{setBusyId('')}
  }

  return (
    <div className="experience-page">
      <section className="experience-hero">
        <div>
          <p className="eyebrow"><Sparkles size={14}/>Reusable research methods</p>
          <h1>经验中心</h1>
          <p>这里只沉淀可复用的方法、边界和反模式。原始问题与回答留在次级运行审计，不会自动变成经验。</p>
        </div>
        <div className="experience-principle"><BookOpenCheck size={20}/><strong>经验不是证据</strong><span>每次使用都会重新查询最新本地材料</span></div>
      </section>

      {governance&&<section className="governance-strip" aria-label="经验治理状态">
        <div><strong>{governance.accepted_count}</strong><span>accepted</span></div>
        <div><strong>{governance.blocked_count}</strong><span>blocked</span></div>
        <div><strong>{governance.conflicts.filter(item=>item.severity==='blocking').length}</strong><span>blocking conflicts</span></div>
        <p>普通成功回答不会自动沉淀；accepted 会版本化导出并按期复验。</p>
      </section>}

      <section className="experience-toolbar" aria-label="经验状态筛选">
        <div><Filter size={15}/>{FILTERS.map(item=>(
          <button key={item.value} className={status===item.value?'active':''} aria-pressed={status===item.value} onClick={()=>setStatus(item.value)}>{item.label}</button>
        ))}</div>
        <button className="refresh" onClick={()=>void load()} disabled={loading}><RefreshCw size={15}/>刷新</button>
      </section>

      {error&&<p className="experience-error" role="alert">{error}</p>}
      {loading&&<p className="experience-empty">正在读取本地经验库…</p>}
      {!loading&&!error&&status==='candidate'&&reviewQueue&&reviewQueue.cards.length>0&&<ExperienceReviewPanel queue={reviewQueue} onApplied={()=>void load()}/>}
      {!loading&&!error&&((status==='candidate'&&reviewQueue?.cards.length===0)||(status!=='candidate'&&experiences.length===0))&&(
        <section className="experience-empty"><h2>当前没有{FILTERS.find(item=>item.value===status)?.label}</h2><p>普通成功回答不会制造候选；只有新的通用方法或失败模式才会进入这里。</p></section>
      )}
      {status!=='candidate'&&<section className="experience-grid" aria-live="polite">
        {experiences.map(experience=><ExperienceCard key={experience.experience_id} experience={experience} busy={busyId===experience.experience_id} onReview={onReview}/>)}
      </section>}
    </div>
  )
}
