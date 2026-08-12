import {Ban, Check, CircleAlert, GitMerge, ShieldCheck} from 'lucide-react'
import {ExperienceDetailList} from './ExperienceDetailList'
import type {Experience} from './types'

const TYPE_LABEL: Record<Experience['experience_type'], string> = {
  routing_rule: '路由规则',
  query_plan: '查询计划',
  definition: '定义口径',
  coverage_boundary: '覆盖边界',
  reasoning_rule: '推理规则',
  presentation_rule: '表达规则',
  anti_pattern: '反模式',
  materialization_recipe: '材料化配方',
  regression_case: '回归案例',
}

const STATUS_LABEL: Record<Experience['status'], string> = {
  candidate:'待审',accepted:'已接受',ignored:'已忽略',merged:'已合并',blocked:'需要证据',
  closed:'已关闭',superseded:'已取代',
}

interface ExperienceCardProps {
  experience: Experience
  busy: boolean
  onReview: (experience: Experience, action: 'accept'|'ignore'|'block'|'close') => void
}

export function ExperienceCard({experience, busy, onReview}: ExperienceCardProps) {
  return (
    <article className="experience-card">
      <header>
        <div className="experience-title">
          <span className={`experience-type type-${experience.experience_type}`}>{TYPE_LABEL[experience.experience_type]}</span>
          <span className={`experience-status status-${experience.status}`}>{STATUS_LABEL[experience.status]}</span>
          <h2>{experience.title}</h2>
        </div>
        <div className="experience-version">v{experience.experience_version}</div>
      </header>
      <p className="experience-value">{experience.value_summary}</p>
      <div className="experience-triggers" aria-label="触发条件">
        {experience.topic_tags.map(value=><span className="topic-tag" key={`topic-${value}`}>{value}</span>)}
        {experience.trigger_conditions.map(value=><span key={value}>{value}</span>)}
      </div>
      <dl className="experience-meta">
        <div><dt>来源运行</dt><dd>{experience.source_run_refs.length}</dd></div>
        <div><dt>必需输入</dt><dd>{experience.required_inputs.length}</dd></div>
        <div><dt>验证</dt><dd>{experience.validation_refs.length}</dd></div>
        <div><dt>证据属性</dt><dd><ShieldCheck size={14}/>非证据</dd></div>
      </dl>
      <details>
        <summary>查看方法、边界与测试</summary>
        <div className="experience-details">
          <ExperienceDetailList title="适用范围" values={experience.scope}/>
          <ExperienceDetailList title="必需输入" values={experience.required_inputs}/>
          <ExperienceDetailList title="查询计划" values={experience.query_plan}/>
          <ExperienceDetailList title="输出要求" values={experience.answer_rubric}/>
          <ExperienceDetailList title="反模式" values={experience.anti_patterns}/>
          <ExperienceDetailList title="覆盖边界" values={experience.coverage_boundaries}/>
          <ExperienceDetailList title="验证测试" values={experience.validation_refs}/>
        </div>
      </details>
      {experience.status === 'candidate' && (
        <footer className="experience-actions">
          <button disabled={busy} className="accept" onClick={()=>onReview(experience,'accept')}><Check size={15}/>人工接受</button>
          <button disabled={busy} onClick={()=>onReview(experience,'block')}><CircleAlert size={15}/>需要更多证据</button>
          <button disabled={busy} onClick={()=>onReview(experience,'ignore')}><Ban size={15}/>忽略</button>
        </footer>
      )}
      {experience.status === 'accepted' && (
        <footer className="accepted-note"><Check size={15}/>已由 {experience.reviewed_by} 人工接受；后续使用仍会重查最新证据。</footer>
      )}
      {experience.status === 'merged' && (
        <footer className="accepted-note"><GitMerge size={15}/>已合并到其他经验。</footer>
      )}
    </article>
  )
}
