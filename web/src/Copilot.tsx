import {FormEvent,useEffect,useMemo,useRef,useState} from 'react'
import {
  AlertTriangle,ArrowRight,BookOpenCheck,Database,ExternalLink,
  FileQuestion,Link2,LoaderCircle,Search,Send,
} from 'lucide-react'
import {Link,useLocation,useNavigate} from 'react-router-dom'
import {ask} from './api'
import {questionLink,readContext,readNavigationFocus} from './context'
import {show} from './display'
import type {
  AnswerCard,Claim,NavigationRef,QuestionCard,ResearchContext,Response,StreamEvent,
} from './types'

function Table({rows}:{rows:Array<Record<string,unknown>>}) {
  const columns=useMemo(
    ()=>Array.from(new Set(rows.flatMap(Object.keys))).filter(key=>key!=='row_id'),
    [rows],
  )
  if(!rows.length)return null
  return <div className="table-scroll" tabIndex={0}><table><thead><tr>
    {columns.map(column=><th key={column}>{show(column)}</th>)}
  </tr></thead><tbody>{rows.map(row=><tr key={String(row.row_id)}>
    {columns.map(column=><td key={column}>{show(row[column])}</td>)}
  </tr>)}</tbody></table></div>
}

function Claims({claims}:{claims:Claim[]}) {
  return claims.length?<section><h2>分析</h2>{claims.map((claim,index)=><article
    className="claim" key={`${claim.backing.ref}-${index}`}
  ><p>{show(claim.text)}</p><small>
    {show(claim.claim_type)} · {show(claim.backing.kind)}: {show(claim.backing.ref)}
  </small></article>)}</section>:null
}

function NavigationItem({item,selected}:{item:NavigationRef;selected:boolean}) {
  return <Link id={item.id} className={`evidence-link kind-${item.kind}${selected?' selected':''}`}
    aria-current={selected?'location':undefined} to={item.href}>
    <span>{show(item.kind)}</span><strong>{show(item.label)}</strong><ArrowRight size={13}/>
  </Link>
}

export function EvidenceNavigation({items,selectedId}:{items:NavigationRef[];selectedId?:string}) {
  if(!items.length)return null
  return <section className="evidence-navigation" aria-label="证据导航">
    <h2><Link2 size={15}/>证据导航</h2>
    <div>{items.map(item=><NavigationItem item={item} selected={item.id===selectedId} key={item.id}/>)}</div>
  </section>
}

function Inspector({card,navigation,selectedId}:{card:AnswerCard;navigation:NavigationRef[];selectedId?:string}) {
  const bySource=(kind:string,source:string)=>navigation.find(
    item=>item.kind===kind&&item.source_ref===source,
  )
  return <aside className="inspector"><header><BookOpenCheck size={17}/><h2>证据检查器</h2></header>
    <section><h3>Lens 调用</h3>{card.lens_invocations.map(invocation=>{
      const releaseId=String(invocation.release_id)
      const nav=bySource('lens',releaseId)
      const content=<><strong>{show(releaseId)}</strong><span>
        {show(invocation.lens_kind)} / {show(invocation.release_role)}
      </span><p>{show(invocation.contributed_section)}</p></>
      return <article key={releaseId}>{nav?<Link to={nav.href}>{content}</Link>:content}</article>
    })}</section>
    <section><h3>新鲜度</h3>{Object.entries(card.source_freshness).map(([key,value])=><div
      className="kv" key={key}
    ><span>{show(key)}</span><strong>{value}</strong></div>)}</section>
    <section><h3>出处</h3>{card.provenance.map(source=>{
      const nav=bySource('provenance',source)
      return nav?<Link id={`${nav.id}-source`} className={`source source-link${nav.id===selectedId?' selected':''}`}
        aria-current={nav.id===selectedId?'location':undefined} to={nav.href} key={source}>{show(source)}</Link>
        :<p className="source" key={source}>{show(source)}</p>
    })}</section>
  </aside>
}

function QuestionCardRow({card,currentContext}:{card:QuestionCard;currentContext:ResearchContext}) {
  const context={
    ...currentContext,
    ...(card.object.kind==='stock'?{symbol:card.object.ref}:{}),
    object_scope:{kind:card.object.kind,ref:card.object.ref},
  }
  return <article className="question-card-row">
    <div><span className={`status-${card.status}`}>{show(card.status)}</span><small>{card.id}</small></div>
    <p>{card.question}</p>
    <Link to={questionLink(context,card.question)} aria-label={`再次研究：${card.question}`}>
      <ArrowRight size={14}/>
    </Link>
  </article>
}

export function QuestionDrawer({response,selectedId,currentContext={}}:{response:Response;selectedId?:string;currentContext?:ResearchContext}) {
  const count=response.question_cards.length+response.data_debt_candidates.length
  return <aside className="question-drawer" aria-label="问题沉淀">
    <header><FileQuestion size={17}/><div><h2>问题沉淀</h2><p>{count} 项候选，本轮不写入证据库</p></div></header>
    {response.question_cards.length>0&&<section><h3>问题卡</h3>
      {response.question_cards.map(card=><QuestionCardRow card={card} currentContext={currentContext} key={card.id}/>)}</section>}
    {response.data_debt_candidates.length>0&&<section><h3>数据债候选</h3>
      {response.data_debt_candidates.map(debt=>{
        const nav=response.navigation_refs.find(
          item=>item.kind==='data_debt'&&item.source_ref===debt.debt_ref,
        )
        const content=<><strong>{debt.debt_ref}</strong><p>{debt.gap}</p><small>影响：{debt.affects}</small></>
        return <article className={`debt-candidate${nav?.id===selectedId?' selected':''}`} key={debt.debt_ref}>
          {nav?<Link id={`${nav.id}-drawer`} aria-current={nav.id===selectedId?'location':undefined}
            to={nav.href}>{content}</Link>:content}
        </article>
      })}</section>}
    {count===0&&<p className="drawer-empty">本次回答没有新增问题或数据债候选。</p>}
  </aside>
}

function Answer({card,claims,navigation,selectedId}:{card:AnswerCard;claims:Claim[];navigation:NavigationRef[];selectedId?:string}) {
  const stock=navigation.find(item=>item.kind==='stock')
  return <article className="answer"><header className="answer-head"><div>
    <p className="eyebrow">{show(card.view)} · 截至 {card.as_of}</p><h1>{card.question}</h1>
  </div>{stock&&<Link className="small-button" to={stock.href}>
    查看个股<ExternalLink size={14}/>
  </Link>}</header>
    <div className="meta"><b>{show(card.evidence_grade)}</b><span>{show(card.sample_scope)}</span></div>
    <EvidenceNavigation items={navigation} selectedId={selectedId}/>
    <Claims claims={claims.length?claims:card.analysis_claims}/>
    <section><h2>证据菜单</h2><Table rows={card.body_rows}/></section>
    {card.lens_gap.length>0&&<div className="callout gap"><AlertTriangle size={18}/><div>
      <h2>Lens 缺口</h2>{card.lens_gap.map(gap=><p key={String(gap.gap_id)}>
        {show(gap.missing_for)}：{show(gap.note)}
      </p>)}</div></div>}
    {card.data_debt.length>0&&<div className="callout debt"><Database size={18}/><div>
      <h2>数据债</h2>{card.data_debt.map(debt=><p key={String(debt.debt_ref)}>
        {show(debt.gap)} · {show(debt.affects)} · {show(debt.debt_ref)}
      </p>)}</div></div>}
    <section className="caveats"><h2>边界</h2>{card.caveats.map(caveat=><p key={caveat}>{show(caveat)}</p>)}</section>
  </article>
}

export function Copilot() {
  const location=useLocation()
  const navigate=useNavigate()
  const context=useMemo(()=>readContext(location.search),[location.search])
  const navigationFocus=useMemo(()=>readNavigationFocus(location.search),[location.search])
  const [question,setQuestion]=useState(context.active_question??'')
  const [events,setEvents]=useState<StreamEvent[]>([])
  const [response,setResponse]=useState<Response|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const activeRequest=useRef<AbortController|null>(null)
  const urlQuestion=useRef(context.active_question)

  useEffect(()=>{
    if(urlQuestion.current===context.active_question)return
    urlQuestion.current=context.active_question
    activeRequest.current?.abort()
    activeRequest.current=null
    setQuestion(context.active_question??'')
    setEvents([]);setResponse(null);setError('');setBusy(false)
  },[context.active_question])
  useEffect(()=>()=>activeRequest.current?.abort(),[])

  const selectedNavigation=response?.navigation_refs.find(item=>(
    navigationFocus?.kind===item.kind&&navigationFocus.ref===item.source_ref
  ))
  useEffect(()=>{
    if(!selectedNavigation)return
    const element=document.getElementById(`${selectedNavigation.id}-source`)
      ??document.getElementById(`${selectedNavigation.id}-drawer`)
      ??document.getElementById(selectedNavigation.id)
    element?.scrollIntoView({block:'nearest'})
  },[selectedNavigation])

  async function submit(event:FormEvent) {
    event.preventDefault()
    const nextQuestion=question.trim()
    if(!nextQuestion||busy)return
    activeRequest.current?.abort()
    const controller=new AbortController()
    activeRequest.current=controller
    urlQuestion.current=nextQuestion
    setEvents([]);setResponse(null);setError('');setBusy(true)
    const params=new URLSearchParams(location.search)
    params.set('question',nextQuestion)
    navigate(`/?${params}`,{replace:true})
    try{
      await ask(nextQuestion,{...context,active_question:nextQuestion},streamEvent=>{
        if(activeRequest.current!==controller)return
        setEvents(current=>[...current,streamEvent])
        if(streamEvent.event==='completed'&&streamEvent.payload.response){
          setResponse(streamEvent.payload.response as unknown as Response)
        }
        if(streamEvent.event==='error')setError(String(streamEvent.payload.message??'研究请求失败'))
      },controller.signal)
    }catch(cause){
      if(activeRequest.current===controller&&!(cause instanceof DOMException&&cause.name==='AbortError')){
        setError(cause instanceof Error?cause.message:'研究服务不可用')
      }
    }finally{
      if(activeRequest.current===controller){activeRequest.current=null;setBusy(false)}
    }
  }

  const stage=events.some(item=>item.event==='completed')?4
    :events.some(item=>item.event==='answer_card')?3
    :events.some(item=>item.event==='routed')?2
    :events.some(item=>item.event==='interpreted')?1:0
  const stageLabels=['解释问题','确定路径','查询证据','校验回答']
  const progressText=busy?`研究进度：${stageLabels[Math.min(stage,3)]}`
    :response?'研究回答已完成校验':''

  return <div className="copilot"><div className="ask-zone"><header className="page-head"><div>
    <p className="eyebrow">私人 ST 历史研究</p><h1>证据问答</h1>
  </div>{context.symbol&&<Link to={`/stocks/${context.symbol}`}>
    {context.symbol}<ArrowRight size={14}/>
  </Link>}</header>
    <form className="composer" onSubmit={submit}><Search size={19}/>
      <textarea aria-label="研究问题" value={question} onChange={event=>setQuestion(event.target.value)}
        placeholder="输入股票、事件或开放研究问题" rows={2}/>
      <button aria-label="提交" disabled={busy||!question.trim()}>
        {busy?<LoaderCircle className="spin" size={18}/>:<Send size={18}/>}</button>
    </form>
    <p className="sr-only" role="status" aria-live="polite">{progressText}</p>
    {events.length>0&&<ol className="stages">{stageLabels.map(
      (label,index)=><li className={index<stage?'done':index===stage&&busy?'active':''} key={label}>{label}</li>,
    )}</ol>}
    {error&&<div className="error" role="alert"><AlertTriangle size={18}/>{error}</div>}
    {!response&&!busy&&!error&&<div className="empty">等待研究问题</div>}
    {response?.degraded_reasons.map(reason=><div className="degraded" role="status" key={reason}>{reason}</div>)}
    {response&&!response.answer_card&&<><div className="fallback">
      <p className="eyebrow">{show(response.route.route)}</p>
      <h2>{show(response.gaps[0]?.description??'当前没有可执行的证据路径')}</h2>
    </div><QuestionDrawer response={response} selectedId={selectedNavigation?.id} currentContext={context}/></>}
  </div>
  {response?.answer_card&&<div className="answer-grid">
    <Answer card={response.answer_card} claims={response.claims} navigation={response.navigation_refs}
      selectedId={selectedNavigation?.id}/>
    <div className="answer-side"><Inspector card={response.answer_card} navigation={response.navigation_refs}
      selectedId={selectedNavigation?.id}/>
      <QuestionDrawer response={response} selectedId={selectedNavigation?.id} currentContext={context}/></div>
  </div>}</div>
}
