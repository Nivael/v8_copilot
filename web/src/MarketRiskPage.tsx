import {useCallback,useEffect,useRef,useState} from 'react'
import {Link,useLocation} from 'react-router-dom'
import {ArrowRight,RefreshCw} from 'lucide-react'
import {ColorType,LineSeries,createChart,type Time} from 'lightweight-charts'
import {getMarketRiskStatus} from './api'
import type {MarketRiskETF,MarketRiskIndex,MarketRiskStatus} from './types'
import './learning.css'
import {ETFShareEventReview} from './ETFShareEventReview'
import {ETFReviewScope} from './ETFReviewScope'
import {ETFDailySourceAudit} from './ETFDailySourceAudit'
import {ETFUnitNAVAudit} from './ETFUnitNAVAudit'
import {ETFAssetIdentity} from './ETFAssetIdentity'
import {ETFRegistrationRules} from './ETFRegistrationRules'
import {MarketCloseReference} from './MarketCloseReference'
import {ETFFundScopeRules} from './ETFFundScopeRules'
import {ETFReportContinuity} from './ETFReportContinuity'
import {ETFName} from './ETFName'
import {ETFNoticeReview} from './ETFNoticeReview'
import {ETFProspectusRules} from './ETFProspectusRules'
import {ETFSZSERecheck} from './ETFSZSERecheck'
import {ETFIssuerHistory} from './ETFIssuerHistory'
import {NodeMarketAudit} from './NodeMarketAudit'
import {ExchangeRiskLists} from './ExchangeRiskLists'
import {SZSESTReference} from './SZSESTReference'
import {SSEHistorySources} from './SSEHistorySources'
import {SSEGapReview} from './SSEGapReview'
import {CombinedBreadthHistory} from './CombinedBreadthHistory'
import {STReconstruction} from './STReconstruction'
import {SSESTNoticeReview} from './SSESTNoticeReview'
import {formatShareCount as shareCount} from './numbers'

const flowLabels:Record<string,string>={estimated:'名义估算，非银行现金流，不能识别资金身份',corporate_actions_unchecked:'份额事件未核验',shares_only:'份额已取得；净值与份额事件待核验',
  share_scope_unverified:'全基金日份额范围未核实',share_precision_unverified:'源端份额精度未核实',share_revision_unverified:'份额最终修订版未核实',missing:'缺少同窗份额或净值'}
const flowStatus=(status:string|undefined)=>status?flowLabels[status]||'核对状态未取得':flowLabels.missing

const pct=(value:number|null|undefined)=>value==null?'—':`${value>0?'+':''}${value.toFixed(2)}%`
const ratio=(value:number|null|undefined)=>value==null?"—":`${value.toFixed(2)}%`
const number=(value:number|null|undefined)=>value==null?'—':value.toLocaleString('zh-CN')
const amount=(value:number|null|undefined)=>value==null?'未发布':`${(value/100_000_000).toFixed(2)} 亿元`
const COLORS=['#3d684d','#a47845','#7e8b91']

function BreadthHistoryPath({points}:{points:NonNullable<MarketRiskStatus['breadth_history']>['points']}){
  const container=useRef<HTMLDivElement>(null)
  useEffect(()=>{
    if(!container.current||!points.length)return
    const chart=createChart(container.current,{autoSize:true,height:260,
      layout:{background:{type:ColorType.Solid,color:'#fafbfa'},textColor:'#758177'},
      grid:{vertLines:{color:'#edf1ec'},horzLines:{color:'#e6ece5'}},
      rightPriceScale:{borderColor:'#cdd8ce',scaleMargins:{top:.05,bottom:.05}},timeScale:{borderColor:'#cdd8ce'},
    })
    for(const [index,group] of ['all','st'].entries()){
      const line=chart.addSeries(LineSeries,{color:COLORS[index],lineWidth:2,priceLineVisible:false,
        priceFormat:{type:'custom',formatter:(value:number)=>`${value.toFixed(1)}%`},
        autoscaleInfoProvider:()=>({priceRange:{minValue:0,maxValue:100}}),
      })
      line.setData(points.map(point=>{const value=(group==='st'?point.st_name_group:point).declining_share_pct
        return value==null?{time:point.date as Time}:{time:point.date as Time,value}}))
    }
    chart.timeScale().fitContent()
    const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(()=>chart.timeScale().fitContent())
    observer?.observe(container.current)
    return()=>{observer?.disconnect();chart.remove()}
  },[points])
  return <div className="market-risk-chart" ref={container} aria-label="深市每日下跌股比例路径"/>
}

function Paths({indices,window,through}:{indices:MarketRiskIndex[];window:number;through:string|null}){
  const container=useRef<HTMLDivElement>(null)
  useEffect(()=>{
    if(!container.current)return
    const chart=createChart(container.current,{autoSize:true,height:260,
      layout:{background:{type:ColorType.Solid,color:'#fafbfa'},textColor:'#758177'},
      grid:{vertLines:{color:'#edf1ec'},horzLines:{color:'#e6ece5'}},
      rightPriceScale:{borderColor:'#cdd8ce'},timeScale:{borderColor:'#cdd8ce'},
    })
    indices.forEach((index,i)=>{
      if(through&&index.through!==through)return
      const key=`return_${window}d_pct` as 'return_5d_pct'|'return_20d_pct'|'return_60d_pct'
      if((window===0?index.recent?.return_pct:index[key])==null)return
      const sessions=window===0?index.recent?.sessions:window
      if(sessions==null)return
      const points=index.path.slice(-sessions-1)
      if(points.length!==sessions+1||points.some(point=>point.close==null||point.close<=0))return
      const start=points[0].close!
      chart.addSeries(LineSeries,{color:COLORS[i%COLORS.length],lineWidth:2,priceLineVisible:false}).setData(
        points.map(point=>({time:point.date as Time,value:point.close!/start*100})),
      )
    })
    chart.timeScale().fitContent()
    const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(()=>chart.timeScale().fitContent())
    observer?.observe(container.current)
    return()=>{observer?.disconnect();chart.remove()}
  },[indices,window,through])
  return <div className="market-risk-chart" ref={container} aria-label={window===0?'近两个月市场基准归一化路径':`${window}个交易日市场基准归一化路径`}/>
}

function ETFSharePath({item,window}:{item:MarketRiskETF|undefined;window:string}){
  const container=useRef<HTMLDivElement>(null)
  const metric=item?.windows[window]
  const ready=metric?.share_change_pct!=null
  useEffect(()=>{
    if(!container.current||!ready)return
    const sessions=metric?.window_sessions??Number(window)
    const points=item?.path?.slice(-sessions-1)??[]
    if(!Number.isFinite(sessions)||points.length!==sessions+1||points.some(point=>point.shares==null||point.shares<=0))return
    const chart=createChart(container.current,{autoSize:true,height:260,
      layout:{background:{type:ColorType.Solid,color:'#fafbfa'},textColor:'#758177'},
      grid:{vertLines:{color:'#edf1ec'},horzLines:{color:'#e6ece5'}},
      rightPriceScale:{borderColor:'#cdd8ce'},timeScale:{borderColor:'#cdd8ce'},
    })
    const start=points[0].shares!
    chart.addSeries(LineSeries,{color:'#3d684d',lineWidth:2,priceLineVisible:false}).setData(
      points.map(point=>({time:point.date as Time,value:point.shares!/start*100})),
    )
    chart.timeScale().fitContent()
    const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(()=>chart.timeScale().fitContent())
    observer?.observe(container.current)
    return()=>{observer?.disconnect();chart.remove()}
  },[item,window,ready,metric?.window_sessions])
  if(!ready||!item?.path)return <p className="learning-empty">所选ETF缺少完整同窗份额，不补值或缩短窗口。</p>
  return <><div className="market-risk-chart" ref={container} aria-label={`${item.code} ${window==='recent'?'近两个月':`${window}个交易日`}公布份额归一化路径`}/><p className="learning-footnote">{item.code} · {metric.window_start} 至 {metric.window_end}，起点归一为100。仅展示源端公布份额的变化，未排除折算等事件；范围不默认等同全基金总额，不代表资金金额或持有人身份。</p></>
}

export function MarketRiskBanner(){
  const [data,setData]=useState<MarketRiskStatus|null>(null)
  useEffect(()=>{const controller=new AbortController();getMarketRiskStatus(controller.signal).then(setData).catch(()=>{});return()=>controller.abort()},[])
  return <aside className="market-risk-banner" aria-label="大盘环境优先核查"><div><strong>先核对大盘环境</strong><span>{data?(data.status==='observed_snapshot'?`市场快照截至 ${data.requested_through}；当前风险尚未校准。`:'当前大盘数据未覆盖，不能由个股节点推断整体风险。'):'大盘数据尚未确认，当前风险未知。'}</span></div><Link to="/market">ETF、市场走势与流动性 <ArrowRight size={14}/></Link></aside>
}

export function MarketRiskPage(){
  const {hash}=useLocation()
  const [data,setData]=useState<MarketRiskStatus|null>(null)
  const [error,setError]=useState('')
  const [loading,setLoading]=useState(true)
  const [chosenWindow,setWindow]=useState(0)
  const [chosenETFWindow,setETFWindow]=useState('recent')
  const recentAvailable=data?.recent_window?.availability==='defined'
  const combinedReady=data?.combined_breadth_history?.availability==='observed'&&data.combined_breadth_history.complete_market_history
  const reconstructionReady=data?.st_reconstruction?.availability==='reconstructed'
  const window=chosenWindow===0&&!recentAvailable?20:chosenWindow
  const etfWindow=chosenETFWindow==='recent'&&!recentAvailable?'5':chosenETFWindow
  const [etfCode,setETFCode]=useState('510300.SH')
  const controller=useRef<AbortController|null>(null)
  const load=useCallback(async()=>{
    controller.current?.abort();const request=new AbortController();controller.current=request
    setLoading(true);setError('');setData(null)
    try{const result=await getMarketRiskStatus(request.signal);if(!request.signal.aborted)setData(result)}
    catch{if(!request.signal.aborted)setError('暂时无法读取市场环境。缺失数据不能视为低风险。')}
    finally{if(!request.signal.aborted)setLoading(false)}
  },[])
  useEffect(()=>{void load();return()=>controller.current?.abort()},[load])
  useEffect(()=>{if(data&&hash)document.getElementById(hash.slice(1))?.scrollIntoView?.({block:"start"})},[data,hash])
  return <div className="learning-page market-risk-page">
    <header className="learning-header"><div><p className="eyebrow">研究工作台 / 大盘环境</p><h1>先看市场，再看节点</h1><p>ETF份额、市场走势、涨跌分布与流动性分别核对。大盘风险独立展示，个股事件不覆盖它。</p></div><button className="learning-refresh" disabled={loading} onClick={()=>void load()}><RefreshCw size={16}/>{loading?'读取中…':'重新核对'}</button></header>
    {loading&&<p role="status" className="learning-loading">正在读取市场快照和数据截止日…</p>}
    {error&&<p role="alert" className="experience-error">{error}</p>}
    {data&&<>
      <section className="market-risk-assessment" aria-label="当前风险可用性"><span>当前大盘风险</span><h2>{data.status==='observed_snapshot'?'已有快照，风险等级待校准':'当前无法确认'}</h2><p>{data.status==='observed_snapshot'?`收盘日目标 ${data.requested_through}；观察日 ${data.observation_date}。各来源分别核对截止日，已取得指数不代表整体风险已测量。`:`观察日 ${data.observation_date}。当前没有通过校验的完整市场快照；市场基准仍为历史背景，ETF份额按下方独立截止日展示。`}</p>
        <MarketCloseReference data={data.close_reference} distance={data.target_close_distance}/>
        {data.market_coverage&&<p>同日市场指数 {data.market_coverage.indices_observed_at_target}/{data.market_coverage.declared_indices}；沪深ST完整核验{data.market_coverage.st_style_at_target?'已通过':'未完成'}；涨跌分布{data.market_coverage.breadth_at_target?'已取得':'未覆盖'}。</p>}
        {data.market_coverage?.historical_breadth_venues_at_target!=null&&<p>同目标日期的历史涨跌分布来源 {data.market_coverage.historical_breadth_venues_at_target}/2；单一交易所不代表沪深整体。</p>}
        {(data.market_coverage?.st_reconstruction_source_venues_at_target??0)>0&&<p>同目标日期的ST重建参考价格来源 {data.market_coverage?.st_reconstruction_source_venues_at_target}/2；沪市逐日成员尚待独立核验，不等同完整ST核验通过。</p>}
        <details className="market-source-notes" open={data.status!=='observed_snapshot'}><summary>来源更新与待核对项</summary>
        {data.public_etf_snapshot?.availability==='observed'&&<p>上交所公开ETF份额已读到 {data.public_etf_snapshot.through}。</p>}
        {data.szse_etf_snapshot?.availability==='observed'&&<p>深交所ETF份额记录已读到 {data.szse_etf_snapshot.through}；最终修订版仍待确认，重读情况见下方复核记录。</p>}
        {data.last_attempt?.status==='failed'&&<p className="market-risk-failure">账户行情源最近更新失败：{data.last_attempt.reason==='provider_token_expired'?'行情接口凭证已过期':data.last_attempt.reason}；请求截至 {data.last_attempt.requested_through}。</p>}
        </details>
      </section>
      <section className="market-risk-order" aria-label="研究顺序"><span>01 大盘环境</span><ArrowRight size={15}/><span>02 ST与小盘风格</span><ArrowRight size={15}/><span>03 个股节点与自身风险</span></section>
      <section aria-label="市场趋势与回撤"><header className="learning-section-head"><div><p className="eyebrow">方向 / 风格 / 流动性</p><h2>市场走势与ST风格覆盖</h2></div><div className="market-risk-windows" aria-label="图表窗口">{recentAvailable&&<button aria-pressed={window===0} onClick={()=>setWindow(0)}>近2个月</button>}{[5,20,60].map(value=><button key={value} aria-pressed={window===value} onClick={()=>setWindow(value)}>{value}日</button>)}</div></header>
        {recentAvailable&&<div className="market-recent-window" aria-label="近两个月实际窗口"><p>近两个月：{data.recent_window?.start} 至 {data.recent_window?.end}，{data.recent_window?.sessions}个交易日跨度。起点为目标起始日或之前最后一个收盘日。</p><div className="market-recent-grid">{data.indices.filter(index=>index.through===data.recent_window?.end&&index.recent?.end===data.recent_window?.end).map(index=><article key={index.code}><span>{index.name} · 窗口收益</span><strong>{pct(index.recent?.return_pct)}</strong><small>窗口最大回撤 {pct(index.recent?.max_drawdown_pct)}</small></article>)}</div>{data.recent_observations&&<p>本窗口指数完整覆盖 {data.recent_observations.index_coverage} 条，其中 {data.recent_observations.declining_indices} 条下跌；同窗ETF份额记录覆盖 {data.recent_observations.etf_share_coverage}/8，增加 {data.recent_observations.increasing_share_records} 只、减少 {data.recent_observations.decreasing_share_records} 只。{data.recent_observations.interpretation}</p>}<p>{data.node_market_comparison?.reason||'此处仅作同窗历史描述，尚未完成节点与大盘因素的独立对照。'}</p></div>}
        <div className="market-risk-legend">{data.indices.map((index,i)=><span key={index.code}><i className={`market-line-${i%3}`}/>{index.name} · 截至 {index.through||'未知'}{index.historical_only?' · 历史快照':''}{data.requested_through&&index.through!==data.requested_through?' · 未入同期图':''}</span>)}</div>
        {data.indices.length>0?<><Paths indices={data.indices} window={window} through={data.requested_through}/><p className="learning-footnote">起点归一为100；仅绘制所选窗口完整且截止日一致的序列。较早的ST历史只保留在表中，不拼接成同期走势；ST等权仅消费覆盖率至少95%的日期。</p><div className="learning-table-wrap"><table className="learning-table market-risk-table"><thead><tr><th scope="col">市场基准</th><th scope="col">5日</th><th scope="col">20日</th><th scope="col">60日</th><th scope="col">60日最大回撤</th><th scope="col">5/20日成交额均值比</th></tr></thead><tbody>{data.indices.map(index=><tr key={index.code}><th scope="row">{index.name}<small>{index.through}</small></th><td>{pct(index.return_5d_pct)}</td><td>{pct(index.return_20d_pct)}</td><td>{pct(index.return_60d_pct)}</td><td>{pct(index.max_drawdown_60d_pct)}</td><td>{index.amount_5d_to_20d_ratio==null?'—':`${index.amount_5d_to_20d_ratio.toFixed(2)} 倍`}</td></tr>)}</tbody></table></div></>:<p className="learning-empty">市场基准缺失，无法计算趋势和回撤。</p>}
      </section>

      <div id="st-reference">{data.st_reconstruction&&<STReconstruction data={data.st_reconstruction} indices={data.indices} noticeReview={data.sse_st_notice_review}/>}</div>
      {data.sse_st_notice_review&&<details className="market-source-notes"><summary>沪市ST公告原文条款核对</summary><SSESTNoticeReview data={data.sse_st_notice_review}/></details>}
      {data.szse_st_reference&&<details className="market-source-notes" open={!reconstructionReady}><summary>深市独立核验的ST样本参考</summary><SZSESTReference data={data.szse_st_reference} indices={data.indices}/></details>}
      {data.combined_breadth_history&&<CombinedBreadthHistory data={data.combined_breadth_history}/>}
      {data.breadth_history&&<details className="market-source-notes" open={!combinedReady}><summary>{combinedReady?'深市名称组与原始日表来源':'历史日表与原始来源'}</summary><section className="learning-freshness" aria-label="历史涨跌分布">
        <header className="learning-section-head"><div><p className="eyebrow">市场宽度 / 历史日表</p><h2>深市历史涨跌分布</h2></div><span>{combinedReady?'本项仅深市原日表':'沪市历史仍缺'}</span></header>
        {data.breadth_history.availability==='observed'?<>
          <p>{data.breadth_history.start} 至 {data.breadth_history.through}，完整核对 {data.breadth_history.observed_days}/{data.breadth_history.expected_days} 个收盘日期。{data.breadth_history.note}</p>
          {data.breadth_history.matches_market_target===false&&<p>历史分布截止日与当前市场目标不同，本图保留自己的实际窗口。</p>}
          <div className="market-risk-legend"><span><i className="market-line-0"/>深市A股 · 下跌占有成交股票</span><span><i className="market-line-1"/>深市当日ST名称组 · 下跌占有成交股票</span></div>
          <BreadthHistoryPath points={data.breadth_history.points}/>
          <p>纵轴为下跌股票占当日有成交股票的比例；名称组每日变化，不串接成ST收益指数，也不把无成交股票当平盘。</p>
          <details className="market-source-notes"><summary>逐日核对（{data.breadth_history.observed_days}个日期）</summary><div className="learning-table-wrap"><table className="learning-table market-history-table"><thead><tr><th scope="col">日期 / 来源内A股</th><th scope="col">有成交 / 无成交</th><th scope="col">上涨 / 下跌 / 平盘</th><th scope="col">下跌比例</th><th scope="col">ST名称组 / 有成交</th><th scope="col">ST组下跌比例</th></tr></thead><tbody>{data.breadth_history.points.map(point=><tr key={point.date}><th scope="row">{point.date}<small>{number(point.listed_source_stocks)}只；原报表{number(point.source_rows)}条</small><small>剔除B股{point.excluded_b_shares}、优先股{point.excluded_preferred_shares}</small></th><td>{number(point.observed_trading_stocks)} / {number(point.nontrading_stocks)}</td><td>{number(point.advancing)} / {number(point.declining)} / {number(point.flat)}</td><td>{ratio(point.declining_share_pct)}</td><td>{number(point.st_name_group.listed_source_stocks)} / {number(point.st_name_group.observed_trading_stocks)}</td><td>{ratio(point.st_name_group.declining_share_pct)}</td></tr>)}</tbody></table></div></details>
          <p><a href={data.breadth_history.source_url} target="_blank" rel="noreferrer">深交所历史日表 ↗</a> · {combinedReady?'此处保留深市原始日表及名称组，沪深合并历史分布见上方。':'当前仅深市完整窗发布，沪深合并历史分布仍待补齐。'}</p>
        </>:<p>历史窗尚未完整发布，暂不展示缩短的曲线。{data.breadth_history.last_recorded_attempt?`最近采集记录已核对 ${data.breadth_history.last_recorded_attempt.completed_days}/${data.breadth_history.last_recorded_attempt.expected_days} 个日期（${new Date(data.breadth_history.last_recorded_attempt.recorded_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}）。`:''}{data.breadth_history.last_recorded_attempt?.status==='failed'?'最近一次采集中断，已核对日期保留用于续采。':''}</p>}
        {data.sse_history_archive&&<SSEHistorySources data={data.sse_history_archive} reconciled={combinedReady}/>}
        {data.sse_gap_review&&<SSEGapReview data={data.sse_gap_review} reconciled={combinedReady}/>}
      </section></details>}

      <section className="learning-freshness" aria-label="ETF份额与申赎"><header className="learning-section-head"><div><p className="eyebrow">资金撤离线索 / ETF样本</p><h2>份额变化与净申赎估算</h2></div><label>ETF观察窗口 <select aria-label="ETF观察窗口" value={etfWindow} onChange={event=>setETFWindow(event.target.value)}>{recentAvailable&&<option value="recent">近2个月</option>}{[1,5,20].map(value=><option key={value} value={String(value)}>{value}个交易日</option>)}</select></label></header>
        <p>固定观察8只沪深300、中证500和中证1000ETF。同窗份额覆盖 {data.etf_aggregate[etfWindow]?.observed_etfs??0}/8{data.etf_aggregate[etfWindow]?.evaluation_through?`，目标截至 ${data.etf_aggregate[etfWindow].evaluation_through}`:''}；不外推全体ETF或机构持仓。净申赎金额需先核对净值和份额折算等事件，当前尚未发布。</p>
        <p>同窗单位净值覆盖 {data.etf_aggregate[etfWindow]?.nav_observed_etfs??0}/8；只用各净值日期对应的单位净值。{data.issuer_nav_snapshot?.availability==='observed'?`基金公司历史净值截至 ${data.issuer_nav_snapshot.through}。`:''}净值齐全后，仍需核对份额事件和最新修订。</p>
        {(data.etf_aggregate[etfWindow]?.revision_unconfirmed_etfs??0)>0&&<p>{data.etf_aggregate[etfWindow].revision_unconfirmed_etfs}只ETF的最新份额修订状态待核对。深交所说明：T日晚间份额仅供参考，以T+1日早间更新为准；尚未取得最终修订标记。</p>}
        <label>份额路径 <select aria-label="ETF份额路径" value={etfCode} onChange={event=>setETFCode(event.target.value)}>{Object.entries(data.parameters.etf_basket).map(([code,group])=><option key={code} value={code}>{code} · {group}</option>)}</select></label>
        <ETFSharePath item={data.etfs.find(item=>item.code===etfCode)} window={etfWindow}/>
        <div className="learning-table-wrap"><table className="learning-table"><thead><tr><th scope="col">ETF / 跟踪组</th><th scope="col">份额变化</th><th scope="col">净申赎金额估算</th><th scope="col">核验状态</th></tr></thead><tbody>{Object.entries(data.parameters.etf_basket).map(([code,group])=>{const item=data.etfs.find(etf=>etf.code===code);const metric=item?.windows[etfWindow];return <tr key={code}><th scope="row"><ETFName code={code}/><small>{group} · 截至 {item?.through||'未取得'}</small>{item?.source==='sse_public'&&<small>上交所日终公布份额</small>}{item?.source==='szse_public'&&<small>深交所份额 · 最终修订版待确认</small>}{item?.nav_through&&<small>净值截至 {item.nav_through}</small>}{item?.nav_source_url&&<small><a href={item.nav_source_url} target="_blank" rel="noreferrer">{item.nav_source}单位净值 ↗</a></small>}</th><td>{pct(metric?.share_change_pct)}{metric?.share_change_ten_thousand!=null&&<small>{metric.share_change_ten_thousand>0?'+':''}{number(metric.share_change_ten_thousand)} 万份</small>}</td><td>{amount(metric?.estimated_net_subscription_yuan)}</td><td>{flowStatus(metric?.status)}{item?.share_revision_unverified&&<small>最新份额最终修订版仍待确认</small>}{(item?.nav_conflict_dates?.length??0)>0&&<small>净值来源有冲突，未采用新来源：{item?.nav_conflict_dates?.join('、')}</small>}{(item?.nav_crosscheck_observations??0)>0&&<small>已与交易所核对 {item?.nav_crosscheck_observations} 个重叠净值日</small>}{metric?.share_change_notional_yuan!=null&&<details><summary>未经份额事件校正的名义额</summary><p>{amount(metric.share_change_notional_yuan)}；不得当作已确认净申赎。</p></details>}</td></tr>})}</tbody></table></div>
        {data.etf_issuer_history&&<ETFIssuerHistory data={data.etf_issuer_history}/>}
        <ETFDailySourceAudit sse={data.public_etf_snapshot?.raw_reconciliation} szse={data.szse_etf_snapshot?.raw_reconciliation} target={data.requested_through}/>
        <ETFUnitNAVAudit data={data.issuer_nav_snapshot?.raw_reconciliation} target={data.requested_through}/>
        <ETFAssetIdentity data={data.etf_asset_identity}/>
        {data.etf_fund_scope_rules&&<ETFFundScopeRules data={data.etf_fund_scope_rules}/>}
        {data.etf_registration_rules&&<ETFRegistrationRules data={data.etf_registration_rules}/>}
      </section>

      {data.etf_review_scope&&<ETFReviewScope data={data.etf_review_scope}/>}
      {data.node_market_input_audit&&<NodeMarketAudit data={data.node_market_input_audit}/>}
      {data.szse_revision_recheck&&<ETFSZSERecheck data={data.szse_revision_recheck}/>}
      {data.etf_notice_review&&<ETFNoticeReview data={data.etf_notice_review}/>}
      {data.etf_prospectus_rules&&<ETFProspectusRules data={data.etf_prospectus_rules}/>}
      <div id="etf-reports">{data.etf_report_continuity&&<ETFReportContinuity data={data.etf_report_continuity}/>}</div>
      {data.etf_quarterly&&<section className="learning-freshness" aria-label="ETF季报份额核对">
        <header className="learning-section-head"><div><p className="eyebrow">季报披露 / 份额范围</p><h2>季报申赎与日表范围核对</h2></div><span>{data.etf_quarterly.period_label||'季度未确定'} · {data.etf_quarterly.observed_reports}/{data.etf_quarterly.declared_etfs}</span></header>
        <p>报告期 {data.etf_quarterly.period_start||'未取得'} 至 {data.etf_quarterly.period_end||'未取得'}。{data.etf_quarterly.note}</p>
        {data.etf_quarterly.capture_completed_at&&<p>本次原文归档完成于 {new Date(data.etf_quarterly.capture_completed_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}（北京时间）；各基金的披露日和PDF页码列于下表。</p>}
        {data.etf_quarterly.observed_reports===0?<p>尚未取得通过当前来源和表内平衡校验的匹配季报。</p>:<div className="learning-table-wrap"><table className="learning-table market-quarterly-table"><thead><tr><th scope="col">ETF / 季报原文</th><th scope="col">季度申购－赎回</th><th scope="col">拆分栏 / 表内平衡</th><th scope="col">期末份额与日表差额</th></tr></thead><tbody>{data.etf_quarterly.reports.map(report=><tr key={report.code}><th scope="row"><ETFName code={report.code}/>{report.availability==='observed'&&<><small>披露于 {report.publication_date}</small><small><a href={report.pdf_url?`${report.pdf_url}#page=${report.table_page}`:report.source_url} target="_blank" rel="noreferrer">季报 · PDF第{report.table_page}页 ↗</a></small><small>{report.audit_status==='report_states_unaudited'?'财务资料未经审计':'审计状态未确认'}</small></>}</th>{report.availability!=='observed'?<td colSpan={3}>匹配季报尚未通过校验</td>:<><td>{shareCount(report.net_subscription_shares)} 份<details><summary>申购、赎回与期初期末</summary><p>期初 {shareCount(report.opening_shares)} 份；申购 {shareCount(report.subscription_shares)} 份；赎回 {shareCount(report.redemption_shares)} 份；期末 {shareCount(report.closing_shares)} 份。</p></details></td><td>原栏 {report.split_entry}<small>表内平衡差 {shareCount(report.accounting_residual_shares)} 份</small><small>横线不自动改写为零事件</small></td><td>{report.daily_comparison?.availability==='observed'?<><span>日表－季报总额 {shareCount(report.daily_comparison.difference_from_report_total)} 份</span><small>日表公布 {shareCount(report.daily_comparison.reported_shares)} 份</small>{report.off_exchange_closing_shares!=null&&<><small>季报期末总额明确包含场外 {shareCount(report.off_exchange_closing_shares)} 份</small><small>从季报总额扣除明示场外份额后，与日表差 {shareCount(report.daily_comparison.difference_after_explicit_off_exchange)} 份</small></>}</>:<span>缺少同日交易所份额，未比较</span>}</td></>}</tr>)}</tbody></table></div>}
        <p>日表按万份披露，本次比较以100份为披露精度参照，源端舍入方式未确认；小额差异仍原样显示。场外附注只用于对应期末的范围核对，不据此修改整个日序列或发布净申赎金额。</p>
      </section>}

      {data.etf_share_events&&<ETFShareEventReview data={data.etf_share_events}/>}
      {data.etf_announcements&&<section className="learning-freshness" aria-label="ETF份额事件核对">
        <header className="learning-section-head"><div><p className="eyebrow">份额事件 / 公告依据</p><h2>公告目录与事件核验分开看</h2></div><span>{data.etf_announcements.availability==='observed'?`目录 ${data.etf_announcements.catalog_etfs}/${data.etf_announcements.declared_etfs}`:'目录尚未通过校验'}</span></header>
        <p>公告检索至 {data.etf_announcements.through||'未取得'} 的采集时点，观察窗 {data.etf_announcements.window_start||'未取得'} 至 {data.etf_announcements.window_end||'未取得'}。已取得目录 {number(data.etf_announcements.record_count)} 条；选中文档项 {number(data.etf_announcements.review_required_count)} 项。</p>
        <p>{data.etf_announcements.note}</p>
        {data.etf_announcements.fulltext&&<p>已提取文本 {number(data.etf_announcements.fulltext.text_available)} / {number(data.etf_announcements.fulltext.required)} 份；{data.etf_announcements.fulltext.availability==='observed'?`缺失或不可读 ${number(data.etf_announcements.fulltext.missing_or_unreadable)} 份`:'提取记录尚未通过当前来源校验'}。文本提取不代表逐页完整或份额事件核验通过，选中文档项与文本提取分别计数。</p>}
        {data.etf_announcements.availability==='observed'&&<div className="learning-table-wrap"><table className="learning-table market-announcement-table"><thead><tr><th scope="col">ETF / 公告来源</th><th scope="col">目录数量</th><th scope="col">最早 / 最近公告</th><th scope="col">选中文档项</th><th scope="col">事件核验</th></tr></thead><tbody>{data.etf_announcements.catalogs.map(catalog=><tr key={catalog.code}><th scope="row"><a href={catalog.source_url} target="_blank" rel="noreferrer">{catalog.code} ↗</a></th><td>{number(catalog.record_count)}</td><td>{catalog.oldest_publication}<small>至 {catalog.newest_publication}</small></td><td><details><summary>查看文档（{catalog.review_required_count}）</summary><ul className="market-announcement-docs">{catalog.required_documents.map(doc=><li key={doc.document_id}><a href={doc.url} target="_blank" rel="noreferrer">{doc.title} ↗</a><small>{doc.published_on} · {doc.review_reason==='historical_share_title'?'历史份额相关标题':'观察窗内或后续披露'}</small></li>)}</ul></details></td><td>指定范围另列；全窗事件尚未验收</td></tr>)}</tbody></table></div>}
        <p>实施计划、取消公告和实施结果都保留在选中材料中。最小申赎单位调整、现金分红与基金总份额折算需分别核对，当前净申赎金额继续未发布。</p>
      </section>}

      <section className="learning-freshness" aria-label="市场宽度">
        <header className="learning-section-head"><div><p className="eyebrow">市场宽度 / 当日收盘横截面</p><h2>风险是否在同步扩散</h2></div><span>{data.breadth.through||'截止日未取得'}</span></header>
        {data.breadth.status==='observed'?<>
          <div className="market-breadth">
            <div><span>有收益记录</span><strong>{number(data.breadth.observed_trading_stocks)}</strong></div>
            <div><span>上涨 / 下跌</span><strong>{number(data.breadth.advancing)} / {number(data.breadth.declining)}</strong></div>
            <div><span>跌幅至少5%</span><strong>{number(data.breadth.declining_5pct_or_more)}</strong></div>
            <div><span>收益中位数</span><strong>{pct(data.breadth.median_return_pct)}</strong></div>
            {data.breadth.source==='exchange_public'&&<>
              <div><span>下跌占有成交股票</span><strong>{data.breadth.declining_share_pct==null?'—':`${data.breadth.declining_share_pct.toFixed(2)}%`}</strong></div>
              <div><span>当日收益算术均值</span><strong>{pct(data.breadth.mean_return_pct)}</strong></div>
              <div><span>停牌或无成交</span><strong>{number(data.breadth.nontrading_stocks)}</strong></div>
              <div><span>来源内A股</span><strong>{number(data.breadth.listed_source_stocks)}</strong></div>
            </>}
          </div>
          <p>{data.breadth.scope} {data.breadth.source==='exchange_public'?`有成交股票中平盘 ${number(data.breadth.flat)} 只。`:''} 报告成交额 {amount(data.breadth.amount_yuan)}。</p>
          {data.breadth.return_basis&&<p className="learning-footnote">{data.breadth.return_basis}</p>}
          {data.breadth.historical_path_available===false&&<p>{data.breadth_history?.availability==='observed'?'已有深市历史日表，沪深合并历史分布仍待补齐；另列的历史图仅覆盖深市。':`当前只有 ${data.breadth.through} 的收盘截面，近两个月的涨跌分布路径仍待补齐；`}单日分布不证明风险持续扩散。</p>}
          {data.breadth.venues&&<div className="learning-table-wrap"><table className="learning-table"><thead><tr><th scope="col">官方来源</th><th scope="col">来源内A股</th><th scope="col">有成交</th><th scope="col">停牌或无成交</th><th scope="col">上涨 / 下跌 / 平盘</th><th scope="col">剔除B股</th><th scope="col">剔除优先股</th></tr></thead><tbody>{data.breadth.venues.map(venue=><tr key={venue.venue}><th scope="row"><a href={venue.url} target="_blank" rel="noreferrer">{venue.label} ↗</a><small>{venue.through} · 原报表 {number(venue.source_rows)} 条</small></th><td>{number(venue.listed_source_stocks)}</td><td>{number(venue.observed_trading_stocks)}</td><td>{number(venue.nontrading_stocks)}</td><td>{number(venue.advancing)} / {number(venue.declining)} / {number(venue.flat)}</td><td>{number(venue.excluded_b_shares)}</td><td>{number(venue.excluded_preferred_shares)}</td></tr>)}</tbody></table></div>}
          {data.breadth.st_name_group&&<div className="market-st-cross-section" aria-label="ST名称分组当日分布"><h3>ST名称分组 · 当日分布</h3><p>{data.breadth.st_name_group.definition}</p><div className="market-breadth">
            <div><span>名称组 / 有成交</span><strong>{number(data.breadth.st_name_group.listed_source_stocks)} / {number(data.breadth.st_name_group.observed_trading_stocks)}</strong></div>
            <div><span>上涨 / 下跌</span><strong>{number(data.breadth.st_name_group.advancing)} / {number(data.breadth.st_name_group.declining)}</strong></div>
            <div><span>当日收益中位数</span><strong>{pct(data.breadth.st_name_group.median_return_pct)}</strong></div>
            <div><span>当日收益算术均值</span><strong>{pct(data.breadth.st_name_group.mean_return_pct)}</strong></div>
          </div><p>当前名称分组只描述当日股票，不回填为历史ST成员；同期ST走势仍需历史成员与价格数据。</p></div>}
        </>:<p className="learning-empty">当日涨跌分布尚未取得，无法判断同步下跌的范围。</p>}
        {data.exchange_risk_membership&&<ExchangeRiskLists data={data.exchange_risk_membership} quoteDate={data.breadth.through}/>}
      </section>

      <section className="learning-freshness market-risk-limits" aria-label="参数与检验边界"><h2>这组参数怎样进入研究</h2><p>先描述大盘环境，再比较ST风格与个股节点。当前参数版本 {data.parameter_version}；尚不设置资金撤退概率、风险权重或交易阈值。</p><ul>{data.limitations.map(limit=><li key={limit}>{limit}</li>)}</ul><p>下一步比较“仅节点”与“节点＋市场环境”，固定样本、同一观察时点和交易日窗口；最近两月只作压力案例，另设独立时段检验，避免按已知结果调权重。</p><div className="market-risk-sources">{data.sources.map(source=><a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a>)}</div></section>
      <footer className="learning-footer">页面重新核对只读取本地快照。当前数据不可用时保留未知，不发布“低风险”或“大资金撤退”的结论。</footer>
    </>}
  </div>
}
