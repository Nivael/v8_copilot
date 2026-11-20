import {Link} from 'react-router-dom'
import {ReadingChart} from './ReadingChart'
import {percent} from './readingFormat'
import type {MarketReading} from './readingTypes'
import {useReadingView} from './useReadingView'
import './reading.css'
import {MarketBreadthSequence} from './MarketBreadthSequence'
import {MarketBreadthReading} from './MarketBreadthReading'
import {MarketPriceContext} from './MarketPriceContext'
import {BroadETFSection} from './BroadETFSection'
import {STFixedNov20} from './STFixedNov20'
import alignment from './stBreadthAlignment.json'
import recentBreadth from './recentMarketBreadth.json'

export function MarketOverview(){
  const {packet,error,busy,reload}=useReadingView<MarketReading>('market')
  const data=packet?.data
  const broad=data?.broad_etf?.availability==='available'?data.broad_etf:null
  const latest=data?.latest_price?.availability==='available'&&data.latest_price.as_of>data.as_of?data.latest_price:null
  const price=latest||data
  const breadth=data?.latest_breadth?.availability==='available'&&data.latest_breadth.as_of>data.as_of?data.latest_breadth:null
  const breadthDay=breadth?.as_of||data?.as_of
  const advancing=breadth?.groups[0]?.advancing_pct??data?.metrics.advancing_pct
  const reasons=data?(latest?[latest.reason,...data.why.slice(1).map(reason=>({...reason,title:`${reason.title} · 截至${data.as_of}`}))]:data.why):[]
  return <div className="reading-page">
    <header className="reading-page-head"><div><p className="reading-kicker">先看环境，再看个股</p><h1>市场判断</h1></div><div className="reading-updated"><span>{data?(latest?`指数收盘截至 ${latest.as_of}`:`收盘数据截至 ${data.as_of}`):'正在读取已保存的判断'}</span><button onClick={reload} disabled={busy}>{busy?'读取中…':'刷新判断'}</button></div></header>
    {error&&<p role="alert" className="reading-error">{error}。{data?'当前保留上次判断。':'请稍后重试。'}</p>}
    {!data||!price?<div className="reading-placeholder" role="status"><h2>正在整理最近的市场判断</h2><p>完成后会显示大盘、ST和ETF的结论。</p></div>:<>
      <section className="reading-verdict" aria-label="已保存的市场价格判断"><span className="reading-stance">{price.stance}</span><h2>{price.headline}</h2><p>{price.summary}</p><a className="reading-text-link" href="#market-reasons">为什么这样判断 ↓</a></section>
      <section className="reading-section" aria-label="市场数据日期与判断范围"><h2>这份判断能说明什么？</h2><p>价格判断截至{price.as_of}；上涨股票占比截至{breadthDay}；下方旧ST走势图截至{data.as_of}；ETF份额与同窗价格截至{broad?.as_of||data.as_of}。刷新只重读已保存资料。</p>{breadth&&alignment.breadth_evidence_sha256===recentBreadth.evidence_sha256&&<p>近期动态ST与大盘的冻结同窗复盘另截至{alignment.reading.common_through}，见下方“大盘转弱后，ST怎样？”。它与旧走势图分别保留日期，不把后来的行情接成旧图，也不是实时更新。</p>}<p>已能核对价格与参与面是否同向走弱。已补11月9—19日两组样本的限价配对及窗口内连续状态；逐股均线覆盖、11月20日限价与实际退出能力尚未接齐，当前不能据此给出完整危机等级或仓位上限。</p><p><a href="#market-breadth-sequence">连续转弱后是否必跌？查看历史反例 →</a></p></section>
      {breadth&&<MarketBreadthReading data={breadth} priceAsOf={price.as_of}/>}
      <STFixedNov20 priceAsOf={price.as_of} priceDigest={latest?.source_digest}/><MarketPriceContext data={latest?.price_context} priceAsOf={price.as_of}/>
      <dl className="reading-metrics"><div><dt>最近一个交易日</dt><dd>{percent(price.metrics.day_change_pct)}</dd></div><div><dt>最近5个交易日</dt><dd>{percent(price.metrics.five_day_change_pct)}</dd></div><div><dt>最近20个交易日</dt><dd>{percent(price.metrics.twenty_day_change_pct)}</dd></div><div><dt>{`上涨股票占比（${breadthDay}）`}</dt><dd>{advancing==null?'待更新':`${advancing.toFixed(1)}%`}</dd></div></dl>
      <section className="reading-section"><header><h2>大盘与ST，放在一起看</h2><p>{data.start} — {data.as_of} · 同期累计涨跌</p></header><ReadingChart series={data.chart} label="大盘与ST走势比较"/><p className="reading-caption">线越低，期间跌幅越大。一次上涨，要放回整段走势里看。</p></section>
      <section className="reading-section reading-reasons" id="market-reasons"><header><h2>这个判断怎么用</h2><p>先判断反弹是否持续，再看ST有没有跟上。</p></header><ol>{reasons.map(reason=><li key={reason.title}><h3>{reason.title}</h3><p>{reason.text}</p><a href={reason.source_url} target={reason.source_url.startsWith('http')?'_blank':undefined} rel="noreferrer">{reason.source_label} ↗</a></li>)}</ol><p className="reading-next">接下来盯：{data.watch_next.join('；')}。</p></section>
      <section className="reading-section" aria-label="ETF资金观察"><header><p className="reading-kicker">ETF资金观察{latest&&` · 份额与同窗价格截至${broad?.as_of||data.as_of}`}</p><h2>{broad?.headline||data.etf.headline}</h2></header><p className="reading-lead">{broad?.interpretation||data.etf.interpretation}</p>{broad&&<BroadETFSection data={broad}/>}<details className="reading-disclosure"><summary>怎么看份额、价格和净流入流出？</summary><p>先看价格：资金进入的同时，市场也可能下跌。再看份额：多只宽基ETF同时缩减份额，才是这一组样本出现普遍收缩的迹象。</p><p>{data.etf.how_to_read}</p><p>{data.etf.cash_estimate_yuan==null?'目前能判断份额的增减，现金净流入流出金额尚未齐备。':`样本净申赎名义估算合计 ${(data.etf.cash_estimate_yuan/1e8).toFixed(2)} 亿元。`}</p><p>这里的“期间涨跌”就是从起点到终点的价格变化；“最近20个交易日”用来观察近月方向。把近期变化和两个月整体走势合起来看，能分清反弹与持续改善。</p>{!broad&&<div className="reading-funds">{data.etf.funds.map(fund=><div key={fund.code}><span><strong>{fund.name}</strong><small>{fund.code} · {fund.group}</small></span><b>{percent(fund.share_change_pct)}<small>期间份额变化</small></b></div>)}</div>}<Link to="/market/evidence#etf-reports">报告原文与逐项依据 ↗</Link></details></section>
      <MarketBreadthSequence/>
      <aside className="reading-crosslink"><div><strong>大盘偏弱，个股的原判断还成立吗？</strong><p>对照沐邦、联光、威领、思科瑞的后续价格、ST参考和原研究，更新经验。</p></div><Link to="/learning">查看跟踪与经验 →</Link></aside>
      <details className="reading-disclosure reading-secondary"><summary>数据口径与更多来源</summary><p>{data.reading_note}</p>{data.source_notes?.map(note=><section key={note.title}><h3>{note.title}</h3><p>{note.text}</p><a href={note.source_url} target="_blank" rel="noreferrer">{note.source_label} ↗</a></section>)}<p>本页读取已核对的收盘快照。刷新会重读本地记录，不代表已取得新的交易日行情。</p><a href="https://etf.sse.com.cn/fund/quertion/" target="_blank" rel="noreferrer">ETF交易与申赎如何区分 · 上交所说明 ↗</a><Link to="/market/evidence">查看完整市场依据 →</Link></details>
    </>}
  </div>
}
