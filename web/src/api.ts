import type {
  Dossier, EvidencePackAuditRecord, Experience, ExperienceGovernanceStatus, ExperienceReviewDecisionExport,
  ExperienceReviewQueue, ExperienceStatus, ResearchContext, ResearchRun, StreamEvent,
} from './types'

export function parseNdjson(buffer: string, chunk: string) {
  const lines = `${buffer}${chunk}`.split('\n')
  const remainder = lines.pop() ?? ''
  return {
    remainder,
    events: lines.map(line => line.trim()).filter(Boolean).map(line => JSON.parse(line) as StreamEvent),
  }
}

export async function ask(
  question: string,
  context: ResearchContext,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
) {
  const {object_scope, ...requestContext} = context
  const object = object_scope ?? (context.symbol ? {kind: 'stock', ref: context.symbol} : null)
  const response = await fetch('/api/v1/answers/stream', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      question,
      object,
      context: Object.keys(requestContext).length ? requestContext : null,
      llm_mode: 'auto',
    }),
    signal,
  })
  if (!response.ok || !response.body) throw new Error(`研究服务返回 ${response.status}`)
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const {value, done} = await reader.read()
    if (done) break
    const parsed = parseNdjson(buffer, decoder.decode(value, {stream: true}))
    buffer = parsed.remainder
    parsed.events.forEach(onEvent)
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as StreamEvent)
}

export async function getDossier(
  symbol: string,
  announcementFocus?: string | null,
  signal?: AbortSignal,
): Promise<Dossier> {
  const query = announcementFocus ? `?announcement_focus=${encodeURIComponent(announcementFocus)}` : ''
  const response = await fetch(`/api/v1/stocks/${encodeURIComponent(symbol)}/dossier${query}`, {signal})
  if (!response.ok) throw new Error(`个股证据服务返回 ${response.status}`)
  return response.json()
}

export async function getExperiences(
  status?: ExperienceStatus,
  signal?: AbortSignal,
): Promise<Experience[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  const response = await fetch(`/api/v1/experiences${query}`, {signal})
  if (!response.ok) throw new Error(`经验服务返回 ${response.status}`)
  return response.json()
}

export async function reviewExperience(
  experienceId: string,
  action: 'accept'|'ignore'|'block'|'close',
): Promise<Experience> {
  const response = await fetch(`/api/v1/experiences/${encodeURIComponent(experienceId)}/review`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action, actor_type: 'human', reviewed_by: 'owner', note: ''}),
  })
  if (!response.ok) throw new Error(`经验审阅返回 ${response.status}`)
  return response.json()
}

export async function getExperienceGovernanceStatus(
  signal?:AbortSignal,
):Promise<ExperienceGovernanceStatus> {
  const response=await fetch('/api/v1/experience-governance/status',{signal})
  if(!response.ok)throw new Error(`经验治理服务返回 ${response.status}`)
  return response.json()
}

export async function getExperienceReviewQueue(signal?:AbortSignal):Promise<ExperienceReviewQueue> {
  const response=await fetch('/api/v1/experience-review/queue?limit=10',{signal})
  if(!response.ok)throw new Error(`经验审阅队列返回 ${response.status}`)
  return response.json()
}

export async function submitExperienceReviewDecisions(
  payload:ExperienceReviewDecisionExport,
):Promise<{review_session_id:string;applied:Array<{card_id:string;status:string;replayed:boolean}>}> {
  const response=await fetch('/api/v1/experience-review/decisions',{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),
  })
  if(!response.ok)throw new Error(`经验批量审阅返回 ${response.status}`)
  return response.json()
}

export async function submitRunFeedback(
  runId:string,
  category:'presentation'|'coverage'|'query_plan'|'anti_pattern'|'no_experience',
  feedbackText:string,
):Promise<{feedback_id:string;experience_candidate:Experience|null}> {
  const response=await fetch(`/api/v1/research/runs/${encodeURIComponent(runId)}/feedback`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({category,feedback_text:feedbackText,submitted_by:'owner'}),
  })
  if(!response.ok)throw new Error(`运行反馈返回 ${response.status}`)
  return response.json()
}

export async function getResearchRuns(signal?: AbortSignal): Promise<ResearchRun[]> {
  const response = await fetch('/api/v1/research/runs?limit=100', {signal})
  if (!response.ok) throw new Error(`运行审计服务返回 ${response.status}`)
  return response.json()
}

export async function getEvidencePack(
  packId:string,
  signal?:AbortSignal,
):Promise<EvidencePackAuditRecord> {
  const response=await fetch(`/api/v1/research/evidence/${encodeURIComponent(packId)}`,{signal})
  if(!response.ok)throw new Error(`EvidencePack 服务返回 ${response.status}`)
  return response.json()
}
