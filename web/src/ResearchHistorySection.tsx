import {useEffect,useState} from 'react'
import {ReadingChart} from './ReadingChart'
import {ResearchCorrectionNotice} from './ResearchCorrectionNotice'
import {percent} from './readingFormat'
import {useReadingView} from './useReadingView'
import type {HistoryDetail,HistoryInventory,HistoryOutcome,HistoryQuestion,HistoryVisual} from './researchHistoryTypes'
import type {ReadingSeries} from './readingTypes'
import './researchHistory.css'

const windows=[['one_day','下一个收盘'],['five_day','5个交易日'],['twenty_day','20个交易日'],['sixty_day','60个交易日'],['latest','至今']] as const
const sourceLabels:Record<string,string>={stock:'个股行情',market:'中证全指',st:'ST板块行情',stock_history:'补充历史行情（腾讯）',stock_earlier_history:'较早行情交叉核对（腾讯）'}
function readable(text:string){return text.replace(/:chatgpt-content-reference\{[^}]*\}/g,'〔原引用见聊天〕').replace(/\[User attached[^\]]*\]/g,marker=>/files?; file contents were not included\]$/.test(marker)?'〔附件文件未随文字档案保存〕':'〔原图未随文字档案保存〕').replace(/<image[\s\S]*?<\/image>/g,'〔原图未随文字档案保存〕').replace(/\*\*/g,'')}
function preview(text:string){return readable(text).replace(/〔(?:原图|附件文件)未随文字档案保存〕/g,'').trim()||(/files?; file contents were not included\]/.test(text)?'附件问题（文字档案未包含文件）':'原图问题（文字档案未包含图片）')}
const excerptSegments=new Intl.Segmenter('zh-CN',{granularity:'grapheme'})
function questionExcerpt(text:string){
  const full=preview(text),compact=full.replace(/\s+/g,' ')
  const characters=[...excerptSegments.segment(compact)].map(part=>part.segment)
  const shortened=characters.length>80
  return {text:shortened?characters.slice(0,79).join('')+'…':compact,canExpand:shortened||compact!==full||text.length>200}
}
function timestamp(value:string){return new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})}
function hasPriceComparison(question:HistoryQuestion){return Object.values(question.outcomes).some(series=>Object.values(series).some(value=>value.change_pct!=null))}
function outcomeText(value?:HistoryOutcome){return value?.change_pct==null?(value?.date?'暂无可比价格':'待后续行情'):percent(value.change_pct)}

function attachmentNote(question:HistoryQuestion){
  let images=Number.isSafeInteger(question.unavailable_attachments)&&(question.unavailable_attachments??0)>0
  let files=false
  if(question.kind==='original_question'&&question.sources.some(source=>source.kind==='chatgpt')){
    let fence:string|null=null
    for(const line of question.question.split(/\r?\n/)){
      const delimiter=/^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1]
      if(delimiter){
        if(!fence)fence=delimiter
        else if(delimiter[0]===fence[0]&&delimiter.length>=fence.length&&!line.slice(line.indexOf(delimiter)+delimiter.length).trim())fence=null
        continue
      }
      if(fence)continue
      const marker=/^\[User attached [1-9]\d* (images?|files?); (image|file) contents were not included\]$/.exec(line)
      if(!marker||!marker[1].startsWith(marker[2]))continue
      if(marker[2]==='image')images=true
      else files=true
    }
  }
  if(question.question_visuals?.length)return files?'可在下方展开图片展示截图；原文件内容仍待补齐。':question.question_context?'已补回附件展示截图，可在下方展开。':'可在下方展开附件展示截图。'
  const subject=question.question_context?'这条追问':'这条原问'
  if(images&&files)return `${subject}的图片和文件内容待补齐。`
  if(files)return `${subject}的附件文件内容待补齐。`
  if(images)return question.question_context?'这条追问附有原图，文字档案未包含图片。':'这条原问的附件画面待补齐。'
  return null
}

function beijingClock(value:string){
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(value))
  const part=(type:Intl.DateTimeFormatPartTypes)=>parts.find(p=>p.type===type)!.value
  return {day:`${part('year')}-${part('month')}-${part('day')}`,minutes:Number(part('hour'))*60+Number(part('minute'))}
}
function comparisonReference(question:HistoryQuestion,observedDays:Set<string>){
  if(!question.anchor_date)return '尚未找到当时可比的有效收盘。'
  if(!question.asked_at)return '提问时刻不详，这是事后按日线作的比较。'
  const asked=beijingClock(question.asked_at)
  const finishedLater=!!question.answer_completed_at&&new Date(question.answer_completed_at)>new Date(question.asked_at)
  const effective=finishedLater?beijingClock(question.answer_completed_at!):asked
  if(finishedLater&&(effective.day!==asked.day||(asked.minutes<15*60&&effective.minutes>=15*60)))return `原回答完成于${timestamp(question.answer_completed_at!)}，采用那时已完成的最近收盘。`
  if(observedDays.has(asked.day)&&asked.minutes>=9*60+30&&asked.minutes<15*60&&question.anchor_date<asked.day)return '盘中提问：数字包含提问前已发生的当日涨跌，不等于问后可赚到的收益。'
  return '从这个有效收盘起，比较后面各窗口的价格变化。'
}

function questionDate(question:HistoryQuestion){return question.time_precision==='range'?`${question.asked_from}—${question.asked_through}（日期待确认）`:question.asked_on||'日期待确认'}
function normalized(text:string){return text.normalize('NFKC').toLocaleLowerCase('zh-CN')}
function matchesSearch(question:HistoryQuestion,terms:string[]){
  if(!terms.length)return true
  const review=question.review
  const text=normalized([questionDate(question),readable(question.question),question.question_context?.question,...(question.research_corrections||[]).flatMap(note=>[note.headline,note.summary]),review?.headline,review?.assessment,...(review?.lessons||[])].filter(Boolean).join(' '))
  return terms.every(term=>text.includes(term))
}

function HistoryVisuals({visuals}:{visuals:HistoryVisual[]}){
  const [open,setOpen]=useState(false)
  return <details className="reading-disclosure history-visuals" onToggle={event=>setOpen(event.currentTarget.open)}><summary>当时看到的附件 · 展示截图</summary><p>从原聊天附件预览保存的画面，供还原当时的信息；不是原始文件，也不代表截图中的说法已核实。</p>{open&&visuals.map(visual=><figure key={visual.attachment_id||visual.sha256}><a href={visual.url} target="_blank" rel="noreferrer"><img src={visual.url} width={visual.width} height={visual.height} alt="原聊天附件展示截图" loading="lazy"/></a><figcaption>{visual.attachment_count&&`附件 ${(visual.attachment_index??0)+1}/${visual.attachment_count} · `}画面归档于 {timestamp(visual.captured_at)} · 北京时间 <a href={visual.source_url} target="_blank" rel="noreferrer">打开原聊天 ↗</a></figcaption></figure>)}</details>
}

function HistoryBody({symbol}:{symbol:string}){
  const {packet,error}=useReadingView<HistoryDetail>(`history/${symbol}`)
  const [selected,setSelected]=useState<string|null>(null)
  const [category,setCategory]=useState('全部')
  const [query,setQuery]=useState('')
  const [includeSaved,setIncludeSaved]=useState(false)
  const data=packet?.data
  if(!data||data.symbol!==symbol||data.availability!=='available')return <p role="status">{error||'正在读取这组原问题和后续走势…'}</p>
  const terms=normalized(query).trim().split(/\s+/).filter(Boolean)
  const questions=data.questions.filter(q=>(includeSaved||q.kind==='original_question')&&(category==='全部'||q.categories.includes(category))&&matchesSearch(q,terms))
  const question=questions.find(q=>q.id===selected)||questions[0]
  const choose=(id:string)=>setSelected(id)
  const categories=[...new Set(data.questions.flatMap(q=>q.categories))]
  const resetFilters=()=>{setQuery('');setCategory('全部');setSelected(null)}
  const filters=<div className="history-filters"><label>研究视角<select aria-label="历史问题分类" value={category} onChange={e=>{setCategory(e.target.value);setSelected(null)}}>{['全部',...categories].map(c=><option key={c}>{c}</option>)}</select></label><label className="history-search">查找问题或经验<input type="search" aria-label="查找历史问题或经验" placeholder="关键词或日期，空格可组合" value={query} onChange={e=>{setQuery(e.target.value);setSelected(null)}}/></label>{query&&<button className="history-clear" onClick={()=>{setQuery('');setSelected(null)}}>清除搜索</button>}<label className="history-checkbox"><input type="checkbox" checked={includeSaved} onChange={e=>setIncludeSaved(e.target.checked)}/>同时显示保存的研究题</label></div>
  if(!question)return <>{filters}<p role="status">{!includeSaved&&data.questions.length>0&&data.questions.every(q=>q.kind==='saved_research')?<>这组暂时只有保存的研究题。<button onClick={()=>{resetFilters();setIncludeSaved(true)}}>显示保存研究</button></>:<>没有符合当前条件的记录。<button onClick={resetFilters}>重置筛选</button></>}</p></>
  const rangeContext=question.time_precision==='range'&&question.asked_from&&question.asked_through&&question.range_context?.kind==='pre_range_common_close'&&question.range_context.reference_date<question.asked_from?question.range_context:undefined
  const chartStart=rangeContext?.reference_date||question.anchor_date
  const series:ReadingSeries[]=Object.entries(data.chart_sources).map(([key,points])=>{
    const anchor=points.find(p=>p.date===chartStart)?.level
    const rebased=anchor?points.filter(p=>p.date>=chartStart!).map(p=>({...p,level:p.level==null?null:p.level/anchor*100})):[]
    return {key,name:key==='stock'?data.name:key==='market'?'中证全指':data.st_name,points:rebased,change_pct:rebased.at(-1)?.level==null?null:rebased.at(-1)!.level!-100}
  })
  const markers=[...new Map(questions.filter(q=>q.anchor_date&&q.anchor_date>=question.anchor_date!).map(q=>[q.anchor_date!,{date:q.anchor_date!,id:q.id,label:`${q.asked_on} 的提问：${readable(q.question).slice(0,60)}`}])).values()].slice(0,16)
  const outcomes=question.outcomes[symbol==='market'?'market':'stock']
  const comparedPoints=data.chart_sources[symbol==='market'?'market':'stock']||[]
  const referenceNote=comparisonReference(question,new Set(comparedPoints.filter(p=>p.level!=null).map(p=>p.date)))
  const questionAttachmentNote=attachmentNote(question)
  const questionTitle=questionExcerpt(question.question)
  const contextTitle=question.question_context?questionExcerpt(question.question_context.question):null
  const review=question.review
  const correctedStudy=question.research_corrections?.some(note=>note.role==='corrected_study')
  const replacementStudy=question.research_corrections?.some(note=>note.role==='replacement_study')
  const awaitingSavedPrices=question.kind==='saved_research'&&!Object.values(outcomes||{}).some(value=>value.change_pct!=null)
  const openCorrection=(id:string)=>{setQuery('');setCategory('全部');if(data.questions.find(q=>q.id===id)?.kind==='saved_research')setIncludeSaved(true);setSelected(id)}
  const argumentOnly=review?.assessment_basis==='original_argument_only'
  const marketBackgroundOnly=argumentOnly&&symbol==='market'
  const answeredIds=new Set(data.questions.filter(q=>q.answers.length).map(q=>q.id))
  const hasFollowup=(q:HistoryQuestion)=>!q.answers.length&&!!q.unanswered_followup&&answeredIds.has(q.unanswered_followup.question_id)
  const followup=hasFollowup(question)?question.unanswered_followup:undefined
  const openFollowup=()=>{if(followup){setQuery('');setCategory('全部');setSelected(followup.question_id)}}
  return <>
    {filters}
    <div className="history-layout"><aside className="history-timeline" aria-label={`${data.name}历史提问`}><p>{questions.length}条记录 · 按提问时间</p>{questions.map(q=><button key={q.id} aria-pressed={q.id===question.id} onClick={()=>choose(q.id)}><time>{questionDate(q)}</time><span>{preview(q.question).slice(0,110)}</span>{q.question_context&&<span className="history-context-preview">这轮在问：{preview(q.question_context.question).slice(0,90)}</span>}<small className={q.research_corrections?.some(note=>note.role==='corrected_study')?'history-corrected-label':undefined}>{q.research_corrections?.some(note=>note.role==='corrected_study')?'保存研究 · 有更正':q.research_corrections?.some(note=>note.role==='replacement_study')?'保存研究 · 修正后的核查':q.review_status==='new_observations'?'已有复盘 · 后续走势已追加':q.previous_review?'依据已更正 · 待重核':q.review_status==='argument_only'?'已复核判断依据 · 未评估回报':q.kind==='saved_research'?'保存研究 · 日期为保存时间':hasFollowup(q)?'当时未单独回复 · 有补充问答':q.review?'已复核旧判断':q.time_precision==='range'?'原问题 · 日期待确认':hasPriceComparison(q)?'原问题 · 走势已对照':'原问题 · 可比行情待补'}</small></button>)}</aside>
      <article key={question.id} className="history-detail" aria-label={`${data.name}历史复盘详情`}>
        {question.research_corrections?.map(note=><ResearchCorrectionNotice key={note.old_run_id+note.role} note={note} onOpen={openCorrection} showOriginal/>)}
        <header><p className="reading-kicker">{question.asked_at?`${timestamp(question.asked_at)} · 北京时间`:question.time_precision==='range'?questionDate(question):`${question.asked_on} · 具体时刻未归档`} · {question.kind==='saved_research'?'保存研究时间':'原提问时间'}{correctedStudy&&' · 旧研究题目含已撤回前提'}</p><h3>{questionTitle.text}</h3>{question.question_context&&contextTitle&&<section className="history-question-context" aria-label="追问背景"><p className="reading-kicker">这轮先前的问题 · {question.question_context.asked_on}</p><blockquote>{contextTitle.text}</blockquote>{contextTitle.canExpand&&<details className="reading-disclosure"><summary>完整背景原问题</summary><p className="reading-prewrap">{readable(question.question_context.question)}</p></details>}<a href={question.question_context.source_url} target="_blank" rel="noreferrer">打开这轮原聊天 ↗</a>{questionAttachmentNote&&<small>{questionAttachmentNote}</small>}</section>}{!question.question_context&&questionAttachmentNote&&<p className="reading-caption">{questionAttachmentNote}</p>}{questionTitle.canExpand&&<details className="reading-disclosure"><summary>完整原问题</summary><p className="reading-prewrap">{readable(question.question)}</p></details>}</header>
        {!correctedStudy&&!replacementStudy&&(review?<div className="history-verdict">{(argumentOnly||review.price_through)&&<p className="history-review-date">{argumentOnly?'仅复核判断依据 · 未评估交易回报':`复盘窗口截至 ${review.price_through}`}{review.focused_symbol&&review.focused_symbol!==symbol&&question.review_focused_name&&` · 主要评估${question.review_focused_name}`}</p>}<strong>{review.headline}</strong><p>{review.assessment}</p><ul>{review.lessons.map(text=><li key={text}>{text}</li>)}</ul>{question.review_status==='new_observations'&&<p className="history-review-update">图表已延伸至{data.as_of}，有更长走势可继续复盘；上面的判断仍对应原评估窗口。</p>}</div>:<p className="history-pending">{question.previous_review?(question.review_status==='original_changed'?'原问题、原回答、追问背景或附件已补正，需要重新复盘。':question.review_status==='review_basis_changed'?'复盘范围或依据已改变，需要重新复盘。':'复盘用到的历史价格已更正，需要重新复盘。'):question.answers.length?(question.time_precision==='range'?'原问题和原回答已保留；日期和原判断仍待复核。':hasPriceComparison(question)?'后续走势已对照；这条原回答的事实与推理仍待逐项复核。':'原问题和原回答已保留；可比后续行情仍待补齐，判断也待复核。'):followup?'这条当时没有单独回复；随后补充的问题已有原回答。':'这条原问题尚未找到对应原回答，不补写当时的判断。'}</p>)}
        {question.previous_review&&<details className="reading-disclosure history-previous"><summary>此前复盘（依据已变）</summary><p>{question.previous_review.assessment_basis==='original_argument_only'?'该版仅复核判断依据，未评估交易回报；':question.previous_review.price_through&&`评估价格截至${question.previous_review.price_through}；`}写于 {timestamp(question.previous_review.reviewed_at)}，保留作历史记录。</p><strong>{question.previous_review.headline}</strong><p>{question.previous_review.assessment}</p><ul>{question.previous_review.lessons.map(text=><li key={text}>{text}</li>)}</ul>{question.previous_review.explanation.map(item=><section key={item.lens}><h4>{item.lens}</h4><p>{item.text}</p>{item.sources?.map(source=><p key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a></p>)}</section>)}</details>}
        <div className="history-original"><p className="reading-kicker">{question.answers[0]?.binding==='shared_turn_answer'?'该轮最终回答（多条提问共同归档）':'当时怎么回答'}</p>{!correctedStudy&&<blockquote>{readable(review?.then_quote||question.answers[0]?.summary||(followup?'这条当时未单独作答':'未找到原回答'))}</blockquote>}{followup&&<p><button className="history-clear" onClick={openFollowup}>查看补充后的提问与原答</button></p>}<details className="reading-disclosure"><summary>{correctedStudy?'展开旧研究原文（含已更正内容）':'展开原回答与聊天来源'}</summary>{question.answer_completed_at&&<p>原回答完成于 {timestamp(question.answer_completed_at)}（北京时间）。</p>}{question.answers.map((answer,index)=><div key={index}><p className="reading-prewrap">{readable(answer.text)}</p>{answer.binding==='shared_turn_answer'&&<p>来源只记录了这{answer.source_question_ids?.length||'多'}条问题所在轮次的最终答复，不能证明逐条回应。</p>}{answer.truncated&&<p>这一份文字截取未包含回答的末尾，请打开原聊天查看。</p>}{answer.links?.filter(link=>/^https?:\/\//.test(link.url)).map((link,i)=><p key={i}><a href={link.url} target="_blank" rel="noreferrer">{link.label||'原回答引用'} ↗</a></p>)}</div>)}{question.sources.filter(s=>s.url).map((source,index)=><p key={index}><a href={source.url} target="_blank" rel="noreferrer">{source.title||'打开原聊天'} ↗</a></p>)}</details></div>
        {!!question.question_visuals?.length&&<HistoryVisuals visuals={question.question_visuals}/>}
        {awaitingSavedPrices?<p className="reading-caption">行情尚未覆盖这份研究保存后的交易日。{(correctedStudy||replacementStudy)&&'可回到当时的原问题查看价格过程。'}</p>:question.time_precision==='range'?<section className="history-range-context" aria-label="提问日期待确认"><h4>提问区间与后来走势</h4><p className="reading-caption">提问发生在 {question.asked_from} 至 {question.asked_through} 之间。{rangeContext&&'阴影标出这段可能的提问时间。'}</p>{rangeContext?<><p className="reading-caption">观察参照：{rangeContext.reference_date}收盘＝100。只比较价格过程，未选定某个提问日计算回报。</p><ReadingChart key={question.id} series={series} label={`${data.name}提问区间与价格观察`} valueMode="index" dateRange={{from:question.asked_from!,through:question.asked_through!}}/></>:<p className="history-pending">尚缺区间之前共同有效的收盘参照，价格观察待补齐；原问题和原回答已保留，不选定某一天计算收益。</p>}</section>:!question.anchor_date?<p className="history-pending">现有行情尚未覆盖可用的比较起点，暂不显示后续收益。原问题和原回答已保留。</p>:<>
        <h4>{argumentOnly?(symbol==='market'?'同期市场背景':'同期价格背景'):'后来怎样了'}</h4>
        {argumentOnly&&<p className="reading-caption">{marketBackgroundOnly?'这里只对照大盘和ST，未计算所筛个股或组合的回报。':'这里只展示该股的同期价格，未用这些涨跌验证本条判断的回报。'}</p>}
        <p className="history-comparison-reference"><strong>{question.anchor_date?`涨跌从${question.anchor_date}收盘算起`:'比较起点待定位'}</strong><span>{referenceNote}</span></p>
        {!argumentOnly&&<div className="history-outcomes">{windows.map(([key,label])=><div key={key}><span>{label}</span><strong>{outcomeText(outcomes?.[key])}</strong><small>{outcomes?.[key]?.date||'后续收盘待更新'}</small></div>)}</div>}
        <ReadingChart key={question.id} series={series} label={`${data.name}从${question.anchor_date||'提问日'}起的${argumentOnly?'背景走势':'后续走势'}`} markers={markers} onMarker={choose} reviewThrough={review?.price_through}/>
        <p className="reading-caption">曲线上圆点可切换到那天的原问题。{symbol==='market'&&'本组只对照大盘和ST；未定位的个股不会猜配行情。'}</p>
        <details className="reading-disclosure"><summary>{argumentOnly?(marketBackgroundOnly?'同期大盘与ST数值':'同期个股、大盘与ST数值'):'同一窗口，大盘和ST分别走了多少？'}</summary><div className="reading-scroll"><table><thead><tr><th>窗口</th>{!marketBackgroundOnly&&<th>{data.name}</th>}<th>中证全指</th><th>{data.st_name}</th>{!marketBackgroundOnly&&<th>相对ST</th>}</tr></thead><tbody>{windows.map(([key,label])=>{const own=outcomes?.[key]?.change_pct,st=question.outcomes.st?.[key]?.change_pct;return <tr key={key}><th scope="row">{label}</th>{!marketBackgroundOnly&&<td>{outcomeText(outcomes?.[key])}</td>}<td>{outcomeText(question.outcomes.market?.[key])}</td><td>{outcomeText(question.outcomes.st?.[key])}</td>{!marketBackgroundOnly&&<td>{own==null||st==null?'—':`${(own-st).toFixed(2)}个百分点`}</td>}</tr>})}</tbody></table></div></details>
        </>}
        {review&&<details className="reading-disclosure history-logic"><summary>{argumentOnly?'为什么这样判断 · 原答与依据':'为什么这样判断 · 大盘 / ST / 个股'}</summary>{review.explanation.map(item=><section key={item.lens}><h4>{item.lens}</h4><p>{item.text}</p>{item.sources?.map(source=><p key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a></p>)}</section>)}<small>复盘于 {timestamp(review.reviewed_at)}。{argumentOnly?'本条只核对原答的依据与推理，未用价格涨跌验收。':'同期涨跌是对照，不是因果贡献比例。'}</small></details>}
        {(question.time_precision!=='range'||rangeContext)&&<details className="reading-disclosure reading-secondary"><summary>价格口径与来源</summary><p>{question.basis_note}</p><p>早期价格使用保存的前复权日线，后期按交易所收盘与前收盘的比值衔接；这是价格路径，不是你的实际交易盈亏。原图未归档的盘口问题不据此认定做T成交或收益。</p>{data.stock_history_note&&<p>{data.stock_history_note}</p>}<p>{data.st_note}</p>{Object.entries(data.source_urls).map(([key,url])=><a key={key} href={url} target="_blank" rel="noreferrer">{sourceLabels[key]||'行情来源'} ↗</a>)}</details>}
      </article></div>
  </>
}

export function ResearchHistorySection(){
  const {packet,error}=useReadingView<HistoryInventory>('history')
  const [symbol,setSymbol]=useState('002514.SZ')
  const data=packet?.data
  useEffect(()=>{if(data?.availability==='available'&&window.location.hash==='#research-history')document.getElementById('research-history')?.scrollIntoView({block:'start'})},[data?.availability])
  return <section id="research-history" className="reading-section research-history" aria-label="历史问题与复盘"><header><p className="reading-kicker">把问过的问题，变成下一次判断的经验</p><h2>历史复盘</h2><p>{data?.availability==='available'?`${data.coverage.original_questions}条原问题 · ${data.coverage.stocks}个标的 · 价格截至${data.as_of}`:'正在找回原问题和研究记录'}</p></header>
    {data?.availability==='available'?<><label className="history-stock-select">选择标的<select value={symbol} onChange={e=>setSymbol(e.target.value)} aria-label="历史复盘标的">{data.stocks.map(s=><option key={s.symbol} value={s.symbol}>{s.name} · {s.original_questions?`${s.original_questions}条原问题`:`${s.saved_research}份保存研究`}</option>)}</select></label><HistoryBody key={symbol} symbol={symbol}/><details className="reading-disclosure reading-secondary"><summary>已找回哪些记录？</summary><p>{data.coverage.source_note}</p><p>另有{data.coverage.saved_research}份保存研究；{data.coverage.reviewed_questions}条已写复盘，含盘中问题的证据边界评估。{data.coverage.argument_only_reviews?`其中${data.coverage.argument_only_reviews}条仅复核原判断依据，未评估交易回报。`:''}其余原问题保留原文、原回答和可比价格，后续继续补核，不把“走势已补齐”算成“论点已验证”。</p></details></>:<p role="status">{error||'历史记录正在整理，请稍后同步。'}</p>}
  </section>
}
