import {useEffect,useState} from 'react'
import {ReadingChart} from './ReadingChart'
import {percent} from './readingFormat'
import {useReadingView} from './useReadingView'
import type {HistoryDetail,HistoryInventory} from './researchHistoryTypes'
import type {ReadingSeries} from './readingTypes'
import './researchHistory.css'

const windows=[['one_day','次日'],['five_day','5个交易日'],['twenty_day','20个交易日'],['sixty_day','60个交易日'],['latest','至今']] as const
const sourceLabels:Record<string,string>={stock:'个股行情',market:'中证全指',st:'ST板块行情',stock_history:'补充历史行情（腾讯）'}
function readable(text:string){return text.replace(/:chatgpt-content-reference\{[^}]*\}/g,'〔原引用见聊天〕').replace(/\[User attached[^\]]*\]/g,'〔原图未随文字档案保存〕').replace(/<image[\s\S]*?<\/image>/g,'〔原图未随文字档案保存〕').replace(/\*\*/g,'')}
function preview(text:string){return readable(text).replace(/〔原图未随文字档案保存〕/g,'').trim()||'原图问题（文字档案未包含图片）'}
function timestamp(value:string){return new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})}

function HistoryBody({symbol}:{symbol:string}){
  const {packet,error}=useReadingView<HistoryDetail>(`history/${symbol}`)
  const [selected,setSelected]=useState<string|null>(null)
  const [category,setCategory]=useState('全部')
  const [includeSaved,setIncludeSaved]=useState(false)
  const data=packet?.data
  if(!data||data.symbol!==symbol||data.availability!=='available')return <p role="status">{error||'正在读取这组原问题和后续走势…'}</p>
  const questions=data.questions.filter(q=>(includeSaved||q.kind==='original_question')&&(category==='全部'||q.categories.includes(category)))
  const question=questions.find(q=>q.id===selected)||questions[0]
  const choose=(id:string)=>setSelected(id)
  const categories=[...new Set(data.questions.flatMap(q=>q.categories))]
  if(!question)return <p>这组暂时只有保存的研究题。<button onClick={()=>setIncludeSaved(true)}>显示保存研究</button></p>
  const series:ReadingSeries[]=Object.entries(data.chart_sources).map(([key,points])=>{
    const anchor=points.find(p=>p.date===question.anchor_date)?.level
    const rebased=anchor?points.filter(p=>p.date>=question.anchor_date!).map(p=>({...p,level:p.level==null?null:p.level/anchor*100})):[]
    return {key,name:key==='stock'?data.name:key==='market'?'中证全指':data.st_name,points:rebased,change_pct:rebased.at(-1)?.level==null?null:rebased.at(-1)!.level!-100}
  })
  const markers=[...new Map(questions.filter(q=>q.anchor_date&&q.anchor_date>=question.anchor_date!).map(q=>[q.anchor_date!,{date:q.anchor_date!,id:q.id,label:`${q.asked_on} 的提问：${readable(q.question).slice(0,60)}`}])).values()].slice(0,16)
  const outcomes=question.outcomes[symbol==='market'?'market':'stock']
  const review=question.review
  return <>
    <div className="history-filters"><label>研究视角<select aria-label="历史问题分类" value={category} onChange={e=>{setCategory(e.target.value);setSelected(null)}}>{['全部',...categories].map(c=><option key={c}>{c}</option>)}</select></label><label className="history-checkbox"><input type="checkbox" checked={includeSaved} onChange={e=>setIncludeSaved(e.target.checked)}/>同时显示保存的研究题</label></div>
    <div className="history-layout"><aside className="history-timeline" aria-label={`${data.name}历史提问`}><p>{questions.length}条记录 · 按提问时间</p>{questions.map(q=><button key={q.id} aria-pressed={q.id===question.id} onClick={()=>choose(q.id)}><time>{q.asked_on}</time><span>{preview(q.question).slice(0,110)}</span>{q.question_context&&<span className="history-context-preview">这轮在问：{preview(q.question_context.question).slice(0,90)}</span>}<small>{q.review_status==='new_observations'?'已有复盘 · 后续走势已追加':q.previous_review?'依据已更正 · 待重核':q.kind==='saved_research'?'保存研究 · 日期为保存时间':q.review?'已复核旧判断':'原问题 · 走势已对照'}</small></button>)}</aside>
      <article key={question.id} className="history-detail" aria-label={`${data.name}历史复盘详情`}>
        <header><p className="reading-kicker">{question.asked_at?`${timestamp(question.asked_at)} · 北京时间`:`${question.asked_on} · 具体时刻未归档`} · {question.kind==='saved_research'?'保存研究时间':'原提问时间'}</p><h3>{preview(question.question).slice(0,200)}</h3>{question.question_context&&<section className="history-question-context" aria-label="追问背景"><p className="reading-kicker">这轮先前的问题 · {question.question_context.asked_on}</p><blockquote>{preview(question.question_context.question).slice(0,200)}</blockquote>{question.question_context.question.length>200&&<details className="reading-disclosure"><summary>完整背景原问题</summary><p className="reading-prewrap">{readable(question.question_context.question)}</p></details>}<a href={question.question_context.source_url} target="_blank" rel="noreferrer">打开这轮原聊天 ↗</a>{!!question.unavailable_attachments&&<small>这条追问附有原图，文字档案未包含图片。</small>}</section>}{question.question.length>200&&<details className="reading-disclosure"><summary>完整原问题</summary><p className="reading-prewrap">{readable(question.question)}</p></details>}</header>
        {review?<div className="history-verdict">{review.price_through&&<p className="history-review-date">复盘窗口截至 {review.price_through}{review.focused_symbol&&review.focused_symbol!==symbol&&question.review_focused_name&&` · 主要评估${question.review_focused_name}`}</p>}<strong>{review.headline}</strong><p>{review.assessment}</p><ul>{review.lessons.map(text=><li key={text}>{text}</li>)}</ul>{question.review_status==='new_observations'&&<p className="history-review-update">图表已延伸至{data.as_of}，有更长走势可继续复盘；上面的判断仍对应原评估窗口。</p>}</div>:<p className="history-pending">{question.previous_review?(question.review_status==='original_changed'?'原问题、原回答或追问背景已补正，需要重新复盘。':'复盘用到的历史价格已更正，需要重新复盘。'):question.answers.length?'后续走势已对照；这条原回答的事实与推理仍待逐项复核。':'这条原问题尚未找到对应原回答，不补写当时的判断。'}</p>}
        {question.previous_review&&<details className="reading-disclosure history-previous"><summary>此前复盘（依据已变）</summary><p>{question.previous_review.price_through&&`评估价格截至${question.previous_review.price_through}；`}写于 {timestamp(question.previous_review.reviewed_at)}，保留作历史记录。</p><strong>{question.previous_review.headline}</strong><p>{question.previous_review.assessment}</p><ul>{question.previous_review.lessons.map(text=><li key={text}>{text}</li>)}</ul>{question.previous_review.explanation.map(item=><section key={item.lens}><h4>{item.lens}</h4><p>{item.text}</p>{item.sources?.map(source=><p key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a></p>)}</section>)}</details>}
        <div className="history-original"><p className="reading-kicker">{question.answers[0]?.binding==='shared_turn_answer'?'该轮最终回答（多条提问共同归档）':'当时怎么回答'}</p><blockquote>{readable(review?.then_quote||question.answers[0]?.summary||'未找到原回答')}</blockquote><details className="reading-disclosure"><summary>展开原回答与聊天来源</summary>{question.answer_completed_at&&<p>原回答完成于 {timestamp(question.answer_completed_at)}（北京时间）。</p>}{question.answers.map((answer,index)=><div key={index}><p className="reading-prewrap">{readable(answer.text)}</p>{answer.binding==='shared_turn_answer'&&<p>来源只记录了这{answer.source_question_ids?.length||'多'}条问题所在轮次的最终答复，不能证明逐条回应。</p>}{answer.truncated&&<p>这一份文字截取未包含回答的末尾，请打开原聊天查看。</p>}{answer.links?.filter(link=>/^https?:\/\//.test(link.url)).map((link,i)=><p key={i}><a href={link.url} target="_blank" rel="noreferrer">{link.label||'原回答引用'} ↗</a></p>)}</div>)}{question.sources.filter(s=>s.url).map((source,index)=><p key={index}><a href={source.url} target="_blank" rel="noreferrer">{source.title||'打开原聊天'} ↗</a></p>)}</details></div>
        <h4>后来怎样了</h4><div className="history-outcomes">{windows.map(([key,label])=><div key={key}><span>{label}</span><strong>{percent(outcomes?.[key]?.change_pct)}</strong><small>{outcomes?.[key]?.change_pct==null?'后续有效收盘待更新':outcomes?.[key]?.date}</small></div>)}</div>
        <ReadingChart key={question.id} series={series} label={`${data.name}从${question.anchor_date||'提问日'}起的后续走势`} markers={markers} onMarker={choose} reviewThrough={review?.price_through}/>
        <p className="reading-caption">{question.time_precision==='day'?`具体时刻不详，以${question.anchor_date||'最近有效交易日'}收盘作事后比较。`:`从当时已完成的最近收盘（${question.anchor_date||'待定位'}）起比较。`}曲线上圆点可切换到那天的原问题。{symbol==='market'&&'本组只对照大盘和ST；未定位的个股不会猜配行情。'}</p>
        <details className="reading-disclosure"><summary>同一窗口，大盘和ST分别走了多少？</summary><div className="reading-scroll"><table><thead><tr><th>窗口</th><th>{data.name}</th><th>中证全指</th><th>{data.st_name}</th><th>相对ST</th></tr></thead><tbody>{windows.map(([key,label])=>{const own=outcomes?.[key]?.change_pct,st=question.outcomes.st?.[key]?.change_pct;return <tr key={key}><th>{label}</th><td>{percent(own)}</td><td>{percent(question.outcomes.market?.[key]?.change_pct)}</td><td>{percent(st)}</td><td>{own==null||st==null?'待更新':`${(own-st).toFixed(2)}个百分点`}</td></tr>})}</tbody></table></div></details>
        {review&&<details className="reading-disclosure history-logic"><summary>为什么这样判断 · 大盘 / ST / 个股</summary>{review.explanation.map(item=><section key={item.lens}><h4>{item.lens}</h4><p>{item.text}</p>{item.sources?.map(source=><p key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a></p>)}</section>)}<small>复盘于 {timestamp(review.reviewed_at)}。同期涨跌是对照，不是因果贡献比例。</small></details>}
        <details className="reading-disclosure reading-secondary"><summary>价格口径与来源</summary><p>{question.basis_note}</p><p>早期价格使用保存的前复权日线，后期按交易所收盘与前收盘的比值衔接；这是价格路径，不是你的实际交易盈亏。原图未归档的盘口问题不据此认定做T成交或收益。</p>{data.stock_history_note&&<p>{data.stock_history_note}</p>}<p>{data.st_note}</p>{Object.entries(data.source_urls).map(([key,url])=><a key={key} href={url} target="_blank" rel="noreferrer">{sourceLabels[key]||'行情来源'} ↗</a>)}</details>
      </article></div>
  </>
}

export function ResearchHistorySection(){
  const {packet,error}=useReadingView<HistoryInventory>('history')
  const [symbol,setSymbol]=useState('002514.SZ')
  const data=packet?.data
  useEffect(()=>{if(data?.availability==='available'&&window.location.hash==='#research-history')document.getElementById('research-history')?.scrollIntoView({block:'start'})},[data?.availability])
  return <section id="research-history" className="reading-section research-history" aria-label="历史问题与复盘"><header><p className="reading-kicker">把问过的问题，变成下一次判断的经验</p><h2>历史复盘</h2><p>{data?.availability==='available'?`${data.coverage.original_questions}条原问题 · ${data.coverage.stocks}个标的 · 价格截至${data.as_of}`:'正在找回原问题和研究记录'}</p></header>
    {data?.availability==='available'?<><label className="history-stock-select">选择标的<select value={symbol} onChange={e=>setSymbol(e.target.value)} aria-label="历史复盘标的">{data.stocks.map(s=><option key={s.symbol} value={s.symbol}>{s.name} · {s.original_questions?`${s.original_questions}条原问题`:`${s.saved_research}份保存研究`}</option>)}</select></label><HistoryBody key={symbol} symbol={symbol}/><details className="reading-disclosure reading-secondary"><summary>已找回哪些记录？</summary><p>{data.coverage.source_note}</p><p>另有{data.coverage.saved_research}份保存研究；{data.coverage.reviewed_questions}条已写复盘，含盘中问题的证据边界评估。其余原问题保留原文、原回答和可比价格，后续继续补核，不把“走势已补齐”算成“论点已验证”。</p></details></>:<p role="status">{error||'历史记录正在整理，请稍后同步。'}</p>}
  </section>
}
