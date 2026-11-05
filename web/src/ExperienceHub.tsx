import {useState} from 'react'
import {Link} from 'react-router-dom'
import {ReadingChart} from './ReadingChart'
import {percent} from './readingFormat'
import type {CaseReading,LearningReading,MarketReading,MethodReading} from './readingTypes'
import {useReadingView} from './useReadingView'
import {methodTitle} from './methodPresentation'
import './reading.css'

function localDate(value:string){return new Date(value).toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'})}
function StockCase({stock,market,methods}:{stock:CaseReading;market:MarketReading;methods:MethodReading[]}){
  const history=stock.history[0]
  const chart=[...(stock.period_path?.length?[{key:stock.symbol,name:stock.name||stock.symbol,points:stock.period_path,change_pct:stock.period_change_pct??null}]:[]),...market.chart]
  const related=methods.filter(method=>stock.used_method_ids?.includes(method.id))
  return <article className="reading-case" aria-label={`${stock.name||stock.symbol}持续跟踪`}>
    <header className="reading-case-head"><div><p className="reading-kicker">持续跟踪 · {stock.research_count}次研究记录</p><h2>{stock.name||stock.symbol}</h2><small className="reading-code">{stock.symbol}</small></div>{stock.last_close!=null&&<div className="reading-price"><strong>{stock.last_close.toFixed(2)}<small>元</small></strong><span>当日 {percent(stock.day_change_pct)} · {stock.as_of}</span></div>}</header>
    {stock.availability!=='available'?<p>价格跟踪正在更新，已保存的研究仍可展开查看。</p>:<><h3 className="reading-case-verdict">{stock.headline}</h3><p>这段时期{stock.name}涨跌{percent(stock.period_change_pct)}，ST参考{percent(market.metrics.st_change_pct)}。大盘走弱之外，它的相对表现也需要单独留意。</p><ReadingChart series={chart} label={`${stock.name}与大盘、ST比较`}/></>}
    <div className="reading-review-grid"><section><p className="reading-kicker">当时怎么判断</p>{history?<><h3>{localDate(history.completed_at)} 的研究结论</h3><p>{history.judgment}</p>{stock.last_research_anchor&&<p className="reading-caption">研究时最近收盘：{stock.last_research_anchor.date}，{stock.last_research_anchor.close?.toFixed(2)}元。{stock.since_research_change_pct!=null?`此后至${stock.as_of}，收盘价变化${percent(stock.since_research_change_pct)}。`:'后续收盘仍待更新。'}</p>}<details className="reading-disclosure"><summary>原研究全文与之前的判断</summary>{stock.history.map(run=><section key={run.run_id} className="reading-history"><h4>{localDate(run.completed_at)}</h4><p className="reading-prewrap">{run.full_answer}</p></section>)}<p className="reading-caption">以上结论对应当时材料日期；新的公告事实需在Codex继续核查。</p></details></>:<p>在Codex里研究这只股票，保存的结论会出现在这里。</p>}</section><section><p className="reading-kicker">现在得到什么经验</p>{stock.review?<><h3>{stock.review.assessment}</h3><ul>{stock.review.takeaways.map(item=><li key={item}>{item}</li>)}</ul><small className="reading-muted">复盘于 {localDate(stock.review.reviewed_at)}</small></>:<><h3>需要结合新资料再复盘</h3><p>价格后续已经更新。下一次在Codex研究时，会把新的判断和takeaway记到这里。</p>{stock.previous_review&&<details className="reading-disclosure"><summary>查看上一版复盘</summary><p>{stock.previous_review.assessment}</p><ul>{stock.previous_review.takeaways.map(item=><li key={item}>{item}</li>)}</ul></details>}</>}</section></div>
    <details className="reading-disclosure"><summary>这次研究用到了哪些经验？</summary>{related.length?related.map(method=><p key={method.id}><a href={`#method-${method.id}`}>{methodTitle(method)} ↓</a></p>):<p>本次尚未记录方法引用。</p>}{stock.source_url&&<a href={stock.source_url} target="_blank" rel="noreferrer">上交所原始行情 ↗</a>}</details>
  </article>
}

export function ExperienceHub(){
  const {packet,error,busy,reload}=useReadingView<LearningReading>('learning')
  const [category,setCategory]=useState('全部')
  const data=packet?.data
  return <div className="reading-page"><header className="reading-page-head"><div><p className="reading-kicker">原判断 → 后续变化 → 新经验</p><h1>跟踪与经验</h1></div><div className="reading-updated"><span>{packet?.as_of?`价格截至 ${packet.as_of}`:'正在读取跟踪记录'}</span><button onClick={reload} disabled={busy}>{busy?'读取中…':'同步记录'}</button></div></header>
    {error&&<p role="alert" className="reading-error">{error}。{data?'当前保留已加载的记录。':'请稍后重试。'}</p>}
    <p className="reading-intro">以后直接在Codex里问。研究结论、个股跟踪和复盘统一收在这里。</p>
    {!data?<div className="reading-placeholder" role="status"><h2>正在读取跟踪与经验</h2><p>已有记录准备好后会直接显示。</p></div>:<>
      {data.cases.length?data.cases.map(stock=><StockCase key={stock.symbol} stock={stock} market={data.market_context} methods={data.methods}/>):<p>还没有持续跟踪的个股。</p>}
      <section className="reading-section" aria-label="分类经验"><header><h2>经验库</h2><p>把个案里学到的方法，带回下一次研究。{data.inventory.accepted}条已采用，{data.inventory.candidate}条待验证。</p></header><div className="reading-filters" role="group" aria-label="经验分类">{['全部',...data.categories].map(item=><button key={item} aria-pressed={category===item} onClick={()=>setCategory(item)}>{item}</button>)}</div>
        <div className="reading-methods">{data.methods.filter(method=>category==='全部'||method.category===category).map(method=><article key={method.id} id={`method-${method.id}`}><div><span>{method.category}</span>{method.status==='candidate'&&<small>待验证</small>}</div><h3>{methodTitle(method)}</h3><p>{method.summary}</p><details><summary>什么时候用 · 研究记录</summary><p>原方法名称：{method.title}</p><ul>{method.when_to_use.map(item=><li key={item}>{item}</li>)}</ul><p>已关联{method.source_run_refs.length}份来源记录。方法会在新的研究中再次核对。</p><Link to={method.status==='candidate'?'/methods?status=candidate':`/methods#${method.id}`}>查看完整方法记录 ↗</Link></details></article>)}</div>
      </section><aside className="reading-crosslink"><div><strong>下一次研究，从市场环境开始</strong><p>{data.market_context.headline}</p></div><Link to="/market">回到市场判断 →</Link></aside><details className="reading-disclosure reading-secondary"><summary>更新状态与方法管理</summary><p>Codex保存研究后，本页会在重新进入、切回窗口或定期重读时同步。行情和复盘各自保留日期。</p><Link to="/system">查看数据更新状态 →</Link><Link to="/methods">管理完整经验记录 →</Link></details>
    </>}
  </div>
}
