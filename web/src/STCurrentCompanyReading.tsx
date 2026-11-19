import {STWeilingStageCheck} from './STWeilingStageCheck'
import type {CurrentExtension} from './STCurrentExtension'

const pct=(value:number|null)=>value==null?'暂缺可比价格':`${value>0?'+':''}${value.toFixed(2)}%`
export function STCurrentCompanyReading({data,symbol,historicalThrough}:{data?:CurrentExtension|null;symbol:string;historicalThrough?:string}){
 const stock=data?.tracked.find(s=>s.symbol===symbol)
 if(!data||!stock||(historicalThrough&&data.through<=historicalThrough))return null
 return <section className="reading-current-observation" aria-label={`${stock.name}后续证据更新`}>
  <p className="reading-kicker">先看后续变化 · 截至{data.through}</p>
  <h3>{stock.name}：新进展推进到哪一步？</h3>
  <p>{data.through}收盘{stock.close.toFixed(2)}元；从{stock.anchor}收盘起，个股{pct(stock.change_pct)}，同期主板ST参考{pct(data.latest.reference_change_pct)}，中证全指{pct(data.latest.market_change_pct)}。</p>
  {!stock.in_main_board_reference&&<p>这只股票不计入主板ST参考。{!stock.still_st?'已经离开ST名单，仍继续保留跟踪。':'所属板块与主板不同。'}</p>}
  {stock.symbol==='002667.SZ'&&<STWeilingStageCheck data={data.stage_followup}/>}
  {stock.events.map(event=><article key={event.id}>
   <h4>{event.title}</h4><p className="reading-caption">{event.published_on}披露</p><p>{event.change}</p>
   <p className="reading-next">接下来核对：{event.watch}</p>
   <details className="reading-disclosure"><summary>查看这项更新的原件</summary><p>文件落款：{event.document_dated_on??'确切落款日期未核得'}；披露日与实际生效、付款或登记日期分别核对。</p>{event.pages.map(page=><p key={page}><a href={event.source.url+'#page='+page} target="_blank" rel="noreferrer">{event.source.title} · 第{page}页 ↗</a></p>)}</details>
  </article>)}
  <p className="reading-caption">以上来自已核新复盘，与下方{historicalThrough?`截至${historicalThrough}`:'价格截止尚未核得'}的旧图表和原判断分开。价格变化不证明公告净影响，原研究没有被改写。</p>
 </section>
}
