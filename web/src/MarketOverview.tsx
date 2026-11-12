import {Link} from 'react-router-dom'
import {ReadingChart} from './ReadingChart'
import {percent} from './readingFormat'
import type {MarketReading} from './readingTypes'
import {useReadingView} from './useReadingView'
import './reading.css'
import {BroadETFSection} from './BroadETFSection'

export function MarketOverview(){
  const {packet,error,busy,reload}=useReadingView<MarketReading>('market')
  const data=packet?.data
  const broad=data?.broad_etf?.availability==='available'?data.broad_etf:null
  const latest=data?.latest_price?.availability==='available'&&data.latest_price.as_of>data.as_of?data.latest_price:null
  const price=latest||data
  const reasons=data?(latest?[latest.reason,...data.why.slice(1).map(reason=>({...reason,title:`${reason.title} · 截至${data.as_of}`}))]:data.why):[]
  return <div className="reading-page">
    <header className="reading-page-head"><div><p className="reading-kicker">先看环境，再看个股</p><h1>市场判断</h1></div><div className="reading-updated"><span>{data?(latest?`指数收盘截至 ${latest.as_of}`:`收盘数据截至 ${data.as_of}`):'正在读取已保存的判断'}</span><button onClick={reload} disabled={busy}>{busy?'读取中…':'刷新判断'}</button></div></header>
    {error&&<p role="alert" className="reading-error">{error}。{data?'当前保留上次判断。':'请稍后重试。'}</p>}
    {!data||!price?<div className="reading-placeholder" role="status"><h2>正在整理最近的市场判断</h2><p>完成后会显示大盘、ST和ETF的结论。</p></div>:<>
      <section className="reading-verdict" aria-label="当前市场判断"><span className="reading-stance">{price.stance}</span><h2>{price.headline}</h2><p>{price.summary}</p><a className="reading-text-link" href="#market-reasons">为什么这样判断 ↓</a></section>
      <dl className="reading-metrics"><div><dt>最近一个交易日</dt><dd>{percent(price.metrics.day_change_pct)}</dd></div><div><dt>最近5个交易日</dt><dd>{percent(price.metrics.five_day_change_pct)}</dd></div><div><dt>最近20个交易日</dt><dd>{percent(price.metrics.twenty_day_change_pct)}</dd></div><div><dt>{latest?`上涨股票占比（${data.as_of}）`:'当日上涨股票占比'}</dt><dd>{data.metrics.advancing_pct==null?'待更新':`${data.metrics.advancing_pct.toFixed(1)}%`}</dd></div></dl>
      <section className="reading-section"><header><h2>大盘与ST，放在一起看</h2><p>{data.start} — {data.as_of} · 同期累计涨跌</p></header><ReadingChart series={data.chart} label="大盘与ST走势比较"/><p className="reading-caption">起点统一为100，比较大盘与ST的累计涨跌。</p></section>
      <section className="reading-section reading-reasons" id="market-reasons"><header><h2>这个判断怎么用</h2><p>先判断反弹是否持续，再看ST有没有跟上。</p></header><ol>{reasons.map(reason=><li key={reason.title}><h3>{reason.title}</h3><p>{reason.text}</p><a href={reason.source_url} target={reason.source_url.startsWith('http')?'_blank':undefined} rel="noreferrer">{reason.source_label} ↗</a></li>)}</ol><p className="reading-next">接下来盯：{data.watch_next.join('；')}。</p></section>
      <section className="reading-section" aria-label="ETF资金观察"><header><p className="reading-kicker">ETF资金观察{latest&&` · 份额与同窗价格截至${broad?.as_of||data.as_of}`}</p><h2>{broad?.headline||data.etf.headline}</h2></header><p className="reading-lead">{broad?.interpretation||data.etf.interpretation}</p>{broad&&<BroadETFSection data={broad}/>}<details className="reading-disclosure"><summary>怎么看份额、价格和净流入流出？</summary><p>份额反映基金发行份数，价格反映市场走势；对照两者的方向，观察样本扩张、收缩和价格修复。</p><p>{data.etf.how_to_read}</p><p>{data.etf.cash_estimate_yuan==null?'目前能判断份额的增减，现金净流入流出金额尚未齐备。':`样本净申赎名义估算合计 ${(data.etf.cash_estimate_yuan/1e8).toFixed(2)} 亿元。`}</p><p>“期间涨跌”从图表起点算至终点；“最近20个交易日”观察近月方向。</p>{!broad&&<div className="reading-funds">{data.etf.funds.map(fund=><div key={fund.code}><span><strong>{fund.name}</strong><small>{fund.code} · {fund.group}</small></span><b>{percent(fund.share_change_pct)}<small>期间份额变化</small></b></div>)}</div>}<Link to="/market/evidence#etf-reports">报告原文与逐项依据 ↗</Link></details></section>
      <aside className="reading-crosslink"><div><strong>大盘偏弱，个股的原判断还成立吗？</strong><p>对照沐邦、联光、威领、思科瑞的后续价格、ST参考和原研究，更新经验。</p></div><Link to="/learning">查看跟踪与经验 →</Link></aside>
      <details className="reading-disclosure reading-secondary"><summary>数据口径与更多来源</summary><p>{data.reading_note}</p>{data.source_notes?.map(note=><section key={note.title}><h3>{note.title}</h3><p>{note.text}</p><a href={note.source_url} target="_blank" rel="noreferrer">{note.source_label} ↗</a></section>)}<p>刷新读取本地收盘快照，行情截止日见页首。</p><a href="https://etf.sse.com.cn/fund/quertion/" target="_blank" rel="noreferrer">ETF交易与申赎如何区分 · 上交所说明 ↗</a><Link to="/market/evidence">查看完整市场依据 →</Link></details>
    </>}
  </div>
}
