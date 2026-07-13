import {FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState} from 'react'
import {
  AlertTriangle, ArrowRight, BookOpenCheck, ExternalLink,
  FileQuestion, History, Link2, PanelRightOpen, Search, Send, X,
} from 'lucide-react'
import {Link, useLocation, useNavigate} from 'react-router-dom'
import {ask} from './api'
import {questionLink, readContext, readNavigationFocus} from './context'
import {show} from './display'
import type {
  AnswerCard, Claim, NavigationRef, QuestionCard, ResearchContext, ResearchNarrative,
  Response, StreamEvent,
} from './types'

/** 空状态示例：覆盖稳定回答矩阵的各类合法路径，让内测用户知道能问什么。 */
const STARTER_QUESTIONS: Array<{tag: string; kind: string; question: string}> = [
  {tag: '查询', kind: 'query', question: '沐邦为什么ST？关键节点是什么？'},
  {tag: '查询', kind: 'query', question: '重整投资人招募之后，下一个公告节点平均多久？'},
  {tag: '查询', kind: 'query', question: 'ST面板自身两周涨跌分布如何？'},
  {tag: '证据', kind: 'evidence', question: '哪些月份对ST面板有日历效应证据？'},
  {tag: '证据', kind: 'evidence', question: '均线回踩lens的证据等级、N和反例是什么？'},
  {tag: '清单', kind: 'checklist', question: '沐邦平台整理期该看哪些窗口？'},
  {tag: '数据债', kind: 'debt', question: '重整路径按省份分层如何？'},
  {tag: '边界', kind: 'boundary', question: '现在能买沐邦吗？'},
]

const RECENT_KEY = 'v8_copilot.recent_questions'
const RECENT_LIMIT = 8

function readRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter(item => typeof item === 'string').slice(0, RECENT_LIMIT) : []
  } catch {
    return []
  }
}

function writeRecent(question: string, current: string[]): string[] {
  const next = [question, ...current.filter(item => item !== question)].slice(0, RECENT_LIMIT)
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next))
  } catch {
    // 本地存储不可用时静默降级：历史只在本次会话内有效。
  }
  return next
}

function CellValue({value}: {value: unknown}) {
  if (typeof value === 'string' && /^https?:\/\//.test(value)) {
    return (
      <a className="source-url" href={value} target="_blank" rel="noreferrer">
        打开原文<ExternalLink size={13}/>
      </a>
    )
  }
  return <>{value == null ? '' : show(value)}</>
}

function Table({rows}: {rows: Array<Record<string, unknown>>}) {
  const columns = useMemo(
    () => Array.from(new Set(rows.flatMap(Object.keys))).filter(key => key !== 'row_id'),
    [rows],
  )
  if (!rows.length) return null
  return (
    <div className="table-scroll" tabIndex={0}>
      <table>
        <thead>
          <tr>{columns.map(column => <th key={column}>{show(column)}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={String(row.row_id)}>
              {columns.map(column => (
                <td key={column}><CellValue value={row[column]}/></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EvidenceTables({rows}: {rows: Array<Record<string, unknown>>}) {
  const groups = useMemo(() => {
    const grouped = new Map<string, Array<Record<string, unknown>>>()
    rows.forEach(row => {
      const label = typeof row['记录类型'] === 'string' ? row['记录类型'] : '证据数据'
      grouped.set(label, [...(grouped.get(label) ?? []), row])
    })
    return Array.from(grouped.entries())
  }, [rows])
  return (
    <>
      {groups.map(([label, group]) => (
        <section className="evidence-table-group" key={label}>
          {groups.length > 1 && <h3>{show(label)}</h3>}
          <Table rows={group}/>
        </section>
      ))}
    </>
  )
}

function ReadableAnalysis({card, claims, narrative, llmUsed, onOpenEvidence}: {
  card: AnswerCard
  claims: Claim[]
  narrative?: ResearchNarrative | null
  llmUsed: boolean
  onOpenEvidence: () => void
}) {
  const primary = claims.filter(claim => claim.claim_type === 'fact' || claim.claim_type === 'inference')
  const auditPhrases = ['本地证据表', 'M6 事件索引', 'pilot 对该股票', '官方公告表提供', '机械计算']
  const narrativePrimary = primary.filter(claim => !auditPhrases.some(phrase => claim.text.includes(phrase)))
  const limits = claims.filter(claim => claim.claim_type === 'caveat' || claim.claim_type === 'data_gap')
  const nextQuestions = claims.filter(claim => claim.claim_type === 'question')
  const readablePrimary = narrativePrimary.length ? narrativePrimary : (primary.length ? primary : claims.slice(0, 1))
  return (
    <section className="readable-analysis">
      <header>
        <div>
          <div className="analysis-kicker">
            <p className="eyebrow">研究回答</p>
            <span className="analysis-mode">{llmUsed ? 'LLM 综合分析' : '本地规则分析'}</span>
          </div>
          <h2>基于当前本地证据，能确认什么</h2>
        </div>
        <button type="button" className="evidence-button" onClick={onOpenEvidence}>
          <PanelRightOpen size={16}/>查看证据与来源
        </button>
      </header>
      {narrative
        ? (
          <>
            <p className="analysis-direct">{show(narrative.direct_answer.text)}</p>
            {narrative.reasoning_steps.length > 0 && (
              <section className="reasoning-chain">
                <h3>判断依据</h3>
                <ol>{narrative.reasoning_steps.map((step, index) => (
                  <li key={`${step.title}-${index}`}>
                    <span>{index + 1}</span>
                    <div><strong>{show(step.title)}</strong><p>{show(step.text)}</p></div>
                  </li>
                ))}</ol>
              </section>
            )}
          </>
        )
        : (
          <div className="analysis-copy">
            {readablePrimary.map((claim, index) => (
              <p key={`${claim.backing.ref}-${index}`}>{show(claim.text)}</p>
            ))}
          </div>
        )}
      <div className="analysis-basis">
        <span>{show(card.evidence_grade)}</span>
        <p>{narrative?.basis_note ?? (card.lens_invocations.length > 0
          ? `本题调用 ${card.lens_invocations.length} 条适用的冻结 Lens；其余内容来自可回链的本地查询。`
          : '本题没有匹配到适用的冻结 Lens；以下内容按描述性查询呈现，不升级为历史先验。')}</p>
      </div>
      {(narrative?.uncertainties.length || limits.length > 0) && (
        <section className="analysis-limits">
          <h3>需要保留的不确定性</h3>
          <ul>{(narrative?.uncertainties ?? limits).map((item, index) => (
            <li key={`limit-${index}`}>{show(item.text)}</li>
          ))}</ul>
        </section>
      )}
      {(narrative?.watch_items.length || nextQuestions.length > 0) && (
        <section className="analysis-next">
          <h3>接下来观察什么</h3>
          <ul>{(narrative?.watch_items ?? nextQuestions).map((item, index) => (
            <li key={`next-${index}`}>{show(item.text)}</li>
          ))}</ul>
        </section>
      )}
    </section>
  )
}

function NavigationItem({item, selected}: {item: NavigationRef; selected: boolean}) {
  return (
    <Link
      id={item.id}
      className={`evidence-link kind-${item.kind}${selected ? ' selected' : ''}`}
      aria-current={selected ? 'location' : undefined}
      to={item.href}
    >
      <span>{show(item.kind)}</span><strong>{show(item.label)}</strong><ArrowRight size={13}/>
    </Link>
  )
}

export function EvidenceNavigation({items, selectedId}: {items: NavigationRef[]; selectedId?: string}) {
  if (!items.length) return null
  return (
    <section className="evidence-navigation" aria-label="证据导航">
      <h2><Link2 size={15}/>证据导航</h2>
      <div>
        {items.map(item => <NavigationItem item={item} selected={item.id === selectedId} key={item.id}/>)}
      </div>
    </section>
  )
}

function Inspector({card, claims, navigation, selectedId, onClose}: {
  card: AnswerCard
  claims: Claim[]
  navigation: NavigationRef[]
  selectedId?: string
  onClose: () => void
}) {
  const bySource = (kind: string, source: string) => navigation.find(
    item => item.kind === kind && item.source_ref === source,
  )
  return (
    <aside className="inspector" aria-label="证据与来源">
      <header>
        <BookOpenCheck size={18}/>
        <div><h2>证据与来源</h2><p>审阅出处、Lens 和原始查询行</p></div>
        <button type="button" className="icon-button" aria-label="关闭证据与来源" onClick={onClose}><X size={17}/></button>
      </header>
      <EvidenceNavigation items={navigation} selectedId={selectedId}/>
      <section>
        <h3>论断回链</h3>
        {(claims.length ? claims : card.analysis_claims).map((claim, index) => (
          <article className="claim-source" key={`${claim.backing.ref}-${index}`}>
            <p>{show(claim.text)}</p>
            <span>{show(claim.backing.kind)} · {show(claim.backing.ref)}</span>
          </article>
        ))}
      </section>
      <section>
        <h3>Lens 调用 · {card.lens_invocations.length}</h3>
        {card.lens_invocations.map(invocation => {
          const releaseId = String(invocation.release_id)
          const nav = bySource('lens', releaseId)
          const content = (
            <>
              <strong>{show(releaseId)}</strong>
              <span>{show(invocation.lens_kind)} / {show(invocation.release_role)}</span>
              <p>{show(invocation.contributed_section)}</p>
            </>
          )
          return <article key={releaseId}>{nav ? <Link to={nav.href}>{content}</Link> : content}</article>
        })}
        {card.lens_invocations.length === 0 && <p className="inspector-empty">本题无适用的冻结 Lens。数据库查询仍可作为描述性证据，但不升级为 Lens 结论。</p>}
      </section>
      {card.lens_gap.length > 0 && (
        <section>
          <h3>Lens 缺口</h3>
          {card.lens_gap.map(gap => (
            <article key={String(gap.gap_id)}><strong>{show(gap.missing_for)}</strong><p>{show(gap.note)}</p></article>
          ))}
        </section>
      )}
      <section>
        <h3>查询证据 · {card.body_rows.length} 行</h3>
        <EvidenceTables rows={card.body_rows}/>
      </section>
      {card.data_debt.length > 0 && (
        <section>
          <h3>数据债 · {card.data_debt.length}</h3>
          {card.data_debt.map(debt => <article key={String(debt.debt_ref)}><strong>{show(debt.gap)}</strong><p>{show(debt.affects)} · {show(debt.debt_ref)}</p></article>)}
        </section>
      )}
      <section>
        <h3>新鲜度</h3>
        {Object.entries(card.source_freshness).map(([key, value]) => (
          <div className="kv" key={key}><span>{show(key)}</span><strong>{value}</strong></div>
        ))}
      </section>
      <section>
        <h3>出处</h3>
        {card.provenance.map(source => {
          const nav = bySource('provenance', source)
          return nav
            ? (
              <Link
                id={`${nav.id}-source`}
                className={`source source-link${nav.id === selectedId ? ' selected' : ''}`}
                aria-current={nav.id === selectedId ? 'location' : undefined}
                to={nav.href}
                key={source}
              >{show(source)}</Link>
            )
            : <p className="source" key={source}>{show(source)}</p>
        })}
      </section>
      <section>
        <h3>回答边界</h3>
        {card.caveats.map(caveat => <p className="source" key={caveat}>{show(caveat)}</p>)}
      </section>
    </aside>
  )
}

function QuestionCardRow({card, currentContext}: {card: QuestionCard; currentContext: ResearchContext}) {
  const context = {
    ...currentContext,
    ...(card.object.kind === 'stock' ? {symbol: card.object.ref} : {}),
    object_scope: {kind: card.object.kind, ref: card.object.ref},
  }
  return (
    <article className="question-card-row">
      <div>
        <span className={`status-${card.status}`}>{show(card.status)}</span>
        <small>{card.id}</small>
      </div>
      <p>{card.question}</p>
      <Link to={questionLink(context, card.question)} aria-label={`再次研究：${card.question}`}>
        <ArrowRight size={14}/>
      </Link>
    </article>
  )
}

export function QuestionDrawer({response, selectedId, currentContext = {}}: {
  response: Response
  selectedId?: string
  currentContext?: ResearchContext
}) {
  const count = response.question_cards.length + response.data_debt_candidates.length
  return (
    <aside className="question-drawer" aria-label="问题沉淀">
      <header>
        <FileQuestion size={17}/>
        <div><h2>问题沉淀</h2><p>{count} 项候选，本轮不写入证据库</p></div>
      </header>
      {response.question_cards.length > 0 && (
        <section>
          <h3>问题卡</h3>
          {response.question_cards.map(card => (
            <QuestionCardRow card={card} currentContext={currentContext} key={card.id}/>
          ))}
        </section>
      )}
      {response.data_debt_candidates.length > 0 && (
        <section>
          <h3>数据债候选</h3>
          {response.data_debt_candidates.map(debt => {
            const nav = response.navigation_refs.find(
              item => item.kind === 'data_debt' && item.source_ref === debt.debt_ref,
            )
            const content = (
              <>
                <strong>{debt.debt_ref}</strong>
                <p>{debt.gap}</p>
                <small>影响：{debt.affects}</small>
              </>
            )
            return (
              <article className={`debt-candidate${nav?.id === selectedId ? ' selected' : ''}`} key={debt.debt_ref}>
                {nav
                  ? (
                    <Link
                      id={`${nav.id}-drawer`}
                      aria-current={nav.id === selectedId ? 'location' : undefined}
                      to={nav.href}
                    >{content}</Link>
                  )
                  : content}
              </article>
            )
          })}
        </section>
      )}
      {count === 0 && <p className="drawer-empty">本次回答没有新增问题或数据债候选。</p>}
    </aside>
  )
}

function Answer({card, claims, narrative, llmUsed, navigation, onOpenEvidence}: {
  card: AnswerCard
  claims: Claim[]
  narrative?: ResearchNarrative | null
  llmUsed: boolean
  navigation: NavigationRef[]
  onOpenEvidence: () => void
}) {
  const stock = navigation.find(item => item.kind === 'stock')
  return (
    <article className="answer">
      <header className="answer-head">
        <div>
          <p className="eyebrow">{show(card.view)} · 截至 {card.as_of}</p>
          <h1>{card.question}</h1>
        </div>
        {stock && <Link className="small-button" to={stock.href}>查看个股<ExternalLink size={14}/></Link>}
      </header>
      <div className="meta">
        <b className={`grade grade-${card.evidence_grade}`}>{show(card.evidence_grade)}</b>
        <span>{show(card.sample_scope)}</span>
      </div>
      <ReadableAnalysis card={card} claims={claims.length ? claims : card.analysis_claims} narrative={narrative} llmUsed={llmUsed} onOpenEvidence={onOpenEvidence}/>
      <footer className="answer-foot">
        <span>{card.body_rows.length} 行查询证据</span>
        <span>{card.lens_invocations.length} 条 Lens 命中</span>
        <span>{card.data_debt.length + card.lens_gap.length} 项缺口</span>
        <button type="button" onClick={onOpenEvidence}>展开审阅材料<ArrowRight size={14}/></button>
      </footer>
    </article>
  )
}

export function Copilot() {
  const location = useLocation()
  const navigate = useNavigate()
  const context = useMemo(() => readContext(location.search), [location.search])
  const navigationFocus = useMemo(() => readNavigationFocus(location.search), [location.search])
  const [question, setQuestion] = useState(context.active_question ?? '')
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [response, setResponse] = useState<Response | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [recent, setRecent] = useState<string[]>(readRecent)
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const activeRequest = useRef<AbortController | null>(null)
  const urlQuestion = useRef(context.active_question)

  useEffect(() => {
    if (urlQuestion.current === context.active_question) return
    urlQuestion.current = context.active_question
    activeRequest.current?.abort()
    activeRequest.current = null
    setQuestion(context.active_question ?? '')
    setEvents([]); setResponse(null); setError(''); setBusy(false); setEvidenceOpen(false)
  }, [context.active_question])
  useEffect(() => () => activeRequest.current?.abort(), [])

  const selectedNavigation = response?.navigation_refs.find(item => (
    navigationFocus?.kind === item.kind && navigationFocus.ref === item.source_ref
  ))
  useEffect(() => {
    if (!selectedNavigation) return
    const element = document.getElementById(`${selectedNavigation.id}-source`)
      ?? document.getElementById(`${selectedNavigation.id}-drawer`)
      ?? document.getElementById(selectedNavigation.id)
    element?.scrollIntoView({block: 'nearest'})
  }, [selectedNavigation])

  async function runQuestion(nextQuestion: string) {
    if (!nextQuestion || (busy && urlQuestion.current === nextQuestion)) return
    activeRequest.current?.abort()
    const controller = new AbortController()
    activeRequest.current = controller
    urlQuestion.current = nextQuestion
    setEvents([]); setResponse(null); setError(''); setBusy(true); setEvidenceOpen(false)
    const params = new URLSearchParams(location.search)
    params.set('question', nextQuestion)
    navigate(`/?${params}`, {replace: true})
    try {
      await ask(nextQuestion, {...context, active_question: nextQuestion}, streamEvent => {
        if (activeRequest.current !== controller) return
        setEvents(current => [...current, streamEvent])
        if (streamEvent.event === 'answer_card' && streamEvent.payload.response) {
          setResponse(streamEvent.payload.response as unknown as Response)
        }
        if (streamEvent.event === 'completed' && streamEvent.payload.response) {
          setResponse(streamEvent.payload.response as unknown as Response)
          setRecent(current => writeRecent(nextQuestion, current))
        }
        if (streamEvent.event === 'error') setError(String(streamEvent.payload.message ?? '研究请求失败'))
      }, controller.signal)
    } catch (cause) {
      if (activeRequest.current === controller && !(cause instanceof DOMException && cause.name === 'AbortError')) {
        setError(cause instanceof Error ? cause.message : '研究服务不可用')
      }
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null
        setBusy(false)
      }
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const nextQuestion = question.trim()
    if (!nextQuestion || busy) return
    void runQuestion(nextQuestion)
  }

  function cancel() {
    activeRequest.current?.abort()
    activeRequest.current = null
    setBusy(false)
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    const nextQuestion = question.trim()
    if (!nextQuestion || busy) return
    void runQuestion(nextQuestion)
  }

  function askStarter(starterQuestion: string) {
    setQuestion(starterQuestion)
    void runQuestion(starterQuestion)
  }

  const stage = events.some(item => item.event === 'completed') ? 4
    : events.some(item => item.event === 'answer_card') ? 3
    : events.some(item => item.event === 'routed') ? 2
    : events.some(item => item.event === 'interpreted') ? 1 : 0
  const stageLabels = ['解释问题', '确定路径', '查询证据', '校验回答']
  const progressText = busy ? `研究进度：${stageLabels[Math.min(stage, 3)]}`
    : response ? '研究回答已完成校验' : ''
  const showStarter = !response && !busy && !error

  return (
    <div className="copilot">
      <div className="ask-zone">
        <header className="page-head">
          <div>
            <p className="eyebrow">私人 ST 历史研究</p>
            <h1>证据问答</h1>
          </div>
          {context.symbol && (
            <Link to={`/stocks/${context.symbol}`}>{context.symbol}<ArrowRight size={14}/></Link>
          )}
        </header>
        <form className="composer" onSubmit={submit}>
          <Search size={19}/>
          <textarea
            aria-label="研究问题"
            value={question}
            onChange={event => setQuestion(event.target.value)}
            onKeyDown={onComposerKeyDown}
            placeholder="输入股票、事件或开放研究问题，回车提交"
            rows={2}
          />
          {busy
            ? (
              <button type="button" aria-label="取消研究" onClick={cancel}>
                <X size={18}/>
              </button>
            )
            : (
              <button aria-label="提交" disabled={!question.trim()}>
                <Send size={18}/>
              </button>
            )}
        </form>
        <p className="sr-only" role="status" aria-live="polite">{progressText}</p>
        {events.length > 0 && (
          <ol className="stages">
            {stageLabels.map((label, index) => (
              <li className={index < stage ? 'done' : index === stage && busy ? 'active' : ''} key={label}>
                {label}
              </li>
            ))}
          </ol>
        )}
        {error && <div className="error" role="alert"><AlertTriangle size={18}/>{error}</div>}
        {showStarter && (
          <div className="starter">
            <p className="starter-title">还没想好？这些问题覆盖了系统的各类合法回答路径：</p>
            <div className="starter-grid">
              {STARTER_QUESTIONS.map(starter => (
                <button
                  type="button"
                  className="starter-item"
                  key={starter.question}
                  onClick={() => askStarter(starter.question)}
                >
                  <span className={`starter-tag tag-${starter.kind}`}>{starter.tag}</span>
                  {starter.question}
                </button>
              ))}
            </div>
            {recent.length > 0 && (
              <>
                <p className="starter-title"><History size={13}/>最近问过</p>
                <div className="recent-list">
                  {recent.map(item => (
                    <button type="button" className="recent-item" key={item} onClick={() => askStarter(item)}>
                      {item}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
        {response?.degraded_reasons.map(reason => (
          <div className="degraded" role="status" key={reason}>{reason}</div>
        ))}
        {response && !response.answer_card && (
          <>
            {response.boundary_rewrite
              ? (
                <section className="boundary-rewrite">
                  <p className="eyebrow">研究边界</p>
                  <h2>{response.boundary_rewrite.message}</h2>
                  <p>{response.boundary_rewrite.why}</p>
                  <button type="button" onClick={() => {
                    setQuestion(response.boundary_rewrite!.rewritten_question)
                    void runQuestion(response.boundary_rewrite!.rewritten_question)
                  }}>
                    改问：{response.boundary_rewrite.rewritten_question}<ArrowRight size={15}/>
                  </button>
                </section>
              )
              : (
                <div className="fallback">
                  <p className="eyebrow">{show(response.route.route)}</p>
                  <h2>{show(response.gaps[0]?.description ?? '当前没有可执行的证据路径')}</h2>
                </div>
              )}
            <QuestionDrawer response={response} selectedId={selectedNavigation?.id} currentContext={context}/>
          </>
        )}
      </div>
      {response?.answer_card && (
        <div className={`answer-workspace${evidenceOpen ? ' evidence-open' : ''}`}>
          <div className="answer-main">
            <Answer
              card={response.answer_card}
              claims={response.claims}
              narrative={response.narrative}
              llmUsed={response.llm_used}
              navigation={response.navigation_refs}
              onOpenEvidence={() => setEvidenceOpen(true)}
            />
            {(response.question_cards.length + response.data_debt_candidates.length) > 0 && (
              <details className="followup-drawer">
                <summary>研究后续 · {response.question_cards.length + response.data_debt_candidates.length} 项候选</summary>
                <QuestionDrawer response={response} selectedId={selectedNavigation?.id} currentContext={context}/>
              </details>
            )}
          </div>
          {evidenceOpen && (
            <Inspector
              card={response.answer_card}
              claims={response.claims}
              navigation={response.navigation_refs}
              selectedId={selectedNavigation?.id}
              onClose={() => setEvidenceOpen(false)}
            />
          )}
        </div>
      )}
    </div>
  )
}
