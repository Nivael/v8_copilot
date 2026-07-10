import { FormEvent, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  BookOpenCheck,
  Database,
  ExternalLink,
  LoaderCircle,
  Search,
  Send,
} from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { streamAnswer } from './api'
import { contextFromSearch } from './context'
import { badgeTone, humanize } from './display'
import type { AnswerCard, Claim, ResearchResponse, StreamEvent } from './types'

const STAGES = ['解释问题', '确定路径', '查询证据', '校验回答']

function MetaBadge({ value }: { value: string }) {
  return <span className={`badge ${badgeTone(value)}`}>{humanize(value)}</span>
}

function Claims({ claims }: { claims: Claim[] }) {
  if (!claims.length) return null
  return (
    <section className="answer-section">
      <h2>分析</h2>
      <div className="claim-list">
        {claims.map((claim, index) => (
          <article className="claim" key={claim.claim_id ?? `${claim.backing.ref}-${index}`}>
            <p>{claim.text}</p>
            <span>{humanize(claim.claim_type)} · {humanize(claim.backing.kind)}: {humanize(claim.backing.ref)}</span>
          </article>
        ))}
      </div>
    </section>
  )
}

function ResultTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  const columns = useMemo(
    () => Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).filter((key) => key !== 'row_id'),
    [rows],
  )
  if (!rows.length) return null
  return (
    <div className="table-scroll" tabIndex={0}>
      <table>
        <thead><tr>{columns.map((column) => <th key={column}>{humanize(column)}</th>)}</tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row.row_id)}>
              {columns.map((column) => <td key={column}><span className="cell-value">{humanize(row[column])}</span></td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AnswerBody({ card, claims }: { card: AnswerCard; claims: Claim[] }) {
  const stock = card.object_ref.match(/stock:(\d{6})/)?.[1]
  return (
    <article className="answer-body">
      <header className="answer-header">
        <div>
          <div className="eyebrow">{humanize(card.view)} · 截至 {card.as_of}</div>
          <h1>{card.question}</h1>
        </div>
        {stock && (
          <Link className="icon-text-button" to={`/stocks/${stock}`}>
            查看个股 <ExternalLink size={15} aria-hidden="true" />
          </Link>
        )}
      </header>
      <div className="meta-line">
        <MetaBadge value={card.evidence_grade} />
        <span>{card.sample_scope}</span>
      </div>
      <Claims claims={claims.length ? claims : card.analysis_claims} />
      <section className="answer-section">
        <h2>证据菜单</h2>
        <ResultTable rows={card.body_rows} />
      </section>
      {!!card.lens_gap.length && (
        <section className="gap-callout">
          <AlertTriangle size={18} aria-hidden="true" />
          <div>
            <h2>Lens 缺口</h2>
            {card.lens_gap.map((gap) => <p key={String(gap.gap_id)}>{humanize(gap.missing_for)}：{humanize(gap.note)}</p>)}
          </div>
        </section>
      )}
      {!!card.data_debt.length && (
        <section className="debt-callout">
          <Database size={18} aria-hidden="true" />
          <div>
            <h2>数据债</h2>
            {card.data_debt.map((debt) => <p key={String(debt.debt_ref)}>{humanize(debt.gap)} · {humanize(debt.affects)} · {humanize(debt.debt_ref)}</p>)}
          </div>
        </section>
      )}
      <section className="answer-section caveats">
        <h2>边界</h2>
        {card.caveats.map((caveat) => <p key={caveat}>{caveat}</p>)}
      </section>
    </article>
  )
}

function EvidenceInspector({ card }: { card: AnswerCard }) {
  return (
    <aside className="inspector" aria-label="证据检查器">
      <div className="inspector-heading"><BookOpenCheck size={17} aria-hidden="true" /><h2>证据检查器</h2></div>
      <section>
        <h3>Lens 调用</h3>
        {card.lens_invocations.length ? card.lens_invocations.map((lens) => (
          <div className="inspector-item" key={String(lens.release_id)}>
            <strong>{humanize(lens.release_id)}</strong>
            <span>{humanize(lens.lens_kind)} / {humanize(lens.release_role)}</span>
            <p>{humanize(lens.contributed_section)}</p>
          </div>
        )) : <p className="muted">无已调用 lens，缺口已在正文说明。</p>}
      </section>
      <section>
        <h3>新鲜度</h3>
        {Object.entries(card.source_freshness).map(([key, value]) => (
          <div className="kv" key={key}><span>{humanize(key)}</span><strong>{value}</strong></div>
        ))}
      </section>
      <section>
        <h3>出处</h3>
        {card.provenance.map((source) => <p className="source" key={source}>{source}</p>)}
      </section>
    </aside>
  )
}

export function CopilotPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const context = useMemo(() => contextFromSearch(location.search), [location.search])
  const [question, setQuestion] = useState(context.active_question ?? '')
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [response, setResponse] = useState<ResearchResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  const stage = events.some((event) => event.event === 'claim_block' || event.event === 'completed')
    ? 4
    : events.some((event) => event.event === 'answer_card') ? 3
      : events.some((event) => event.event === 'routed') ? 2
        : events.some((event) => event.event === 'interpreted') ? 1 : 0

  async function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || running) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setEvents([])
    setResponse(null)
    setError('')
    setRunning(true)
    const params = new URLSearchParams(location.search)
    params.set('question', trimmed)
    navigate(`/?${params.toString()}`, { replace: true })
    try {
      await streamAnswer(trimmed, { ...context, active_question: trimmed }, (next) => {
        setEvents((current) => [...current, next])
        if (next.event === 'completed') {
          const finalResponse = next.payload.response as ResearchResponse | undefined
          if (finalResponse) setResponse(finalResponse)
        }
        if (next.event === 'error') setError(String(next.payload.message ?? '研究请求失败'))
      }, controller.signal)
    } catch (caught) {
      if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : '研究服务不可用')
    } finally {
      setRunning(false)
    }
  }

  const fallback = response?.fallback
  const card = response?.answer_card
  const suggestedQuestion = typeof fallback?.suggested_question === 'string'
    ? fallback.suggested_question
    : ''

  return (
    <div className="copilot-page">
      <section className="copilot-workspace">
        <header className="workspace-heading">
          <div>
            <p className="eyebrow">私人 ST 历史研究</p>
            <h1>证据问答</h1>
          </div>
          {context.symbol && <Link className="context-link" to={`/stocks/${context.symbol}`}>{context.symbol}<ArrowRight size={15} /></Link>}
        </header>

        <form className="composer" onSubmit={submit}>
          <Search size={19} aria-hidden="true" />
          <textarea
            aria-label="研究问题"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="输入股票、事件或开放研究问题"
            rows={2}
          />
          <button className="send-button" type="submit" disabled={running || !question.trim()} title="提交研究问题">
            {running ? <LoaderCircle className="spin" size={18} aria-hidden="true" /> : <Send size={18} aria-hidden="true" />}
            <span className="sr-only">提交</span>
          </button>
        </form>

        {(running || events.length > 0) && (
          <ol className="stage-strip" aria-label="回答进度">
            {STAGES.map((label, index) => <li className={index < stage ? 'done' : index === stage && running ? 'active' : ''} key={label}>{label}</li>)}
          </ol>
        )}

        {error && <div className="service-error" role="alert"><AlertTriangle size={18} />{error}</div>}
        {!response && !running && !error && (
          <div className="empty-receipt"><span>等待研究问题</span></div>
        )}
        {fallback && (
          <section className={`fallback ${String(fallback.kind)}`}>
            <span className="eyebrow">{humanize(response?.route.route)}</span>
            <h2>{humanize(fallback.title)}</h2>
            <p>{humanize(fallback.message)}</p>
            {suggestedQuestion && (
              <button type="button" className="text-action" onClick={() => setQuestion(suggestedQuestion)}>
                {suggestedQuestion} <ArrowRight size={15} />
              </button>
            )}
          </section>
        )}
        {response?.degradations.map((item) => <div className="degraded" key={item.code}>{item.message}</div>)}
      </section>

      {card && (
        <div className="answer-layout">
          <AnswerBody card={card} claims={response?.claims ?? []} />
          <EvidenceInspector card={card} />
        </div>
      )}
    </div>
  )
}
