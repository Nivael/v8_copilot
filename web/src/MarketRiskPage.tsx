import {useCallback,useEffect,useRef,useState} from 'react'
import {Link} from 'react-router-dom'
import {ArrowRight,RefreshCw} from 'lucide-react'
import {ColorType,LineSeries,createChart,type Time} from 'lightweight-charts'
import {getMarketRiskStatus} from './api'
import type {MarketRiskIndex,MarketRiskStatus} from './types'
import './learning.css'

const pct=(value:number|null|undefined)=>value==null?'—':`${value>0?'+':''}${value.toFixed(2)}%`
const number=(value:number|null|undefined)=>value==null?'—':value.toLocaleString('zh-CN')
const amount=(value:number|null|undefined)=>value==null?'未发布':`${(value/100_000_000).toFixed(2)} 亿元`
const COLORS=['#3d684d','#a47845','#7e8b91']

function Paths({indices,window}:{indices:MarketRiskIndex[];window:number}){
  const container=useRef<HTMLDivElement>(null)
  useEffect(()=>{
    if(!container.current)return
    const chart=createChart(container.current,{autoSize:true,height:260,
      layout:{background:{type:ColorType.Solid,color:'#fafbfa'},textColor:'#758177'},
      grid:{vertLines:{color:'#edf1ec'},horzLines:{color:'#e6ece5'}},
      rightPriceScale:{borderColor:'#cdd8ce'},timeScale:{borderColor:'#cdd8ce'},
    })
    indices.forEach((index,i)=>{
      const key=`return_${window}d_pct` as 'return_5d_pct'|'return_20d_pct'|'return_60d_pct'
      if(index[key]==null)return
      const points=index.path.slice(-window-1)
      if(points.length!==window+1||points.some(point=>point.close==null||point.close<=0))return
      const start=points[0].close!
      chart.addSeries(LineSeries,{color:COLORS[i%COLORS.length],lineWidth:2,priceLineVisible:false}).setData(
        points.map(point=>({time:point.date as Time,value:point.close!/start*100})),
      )
    })
    chart.timeScale().fitContent()
    return()=>chart.remove()
  },[indices,window])
  return <div className="market-risk-chart" ref={container} aria-label={`${window}个交易日市场基准归一化路径`}/>
}

export function MarketRiskBanner(){
  const [data,setData]=useState<MarketRiskStatus|null>(null)
  useEffect(()=>{const controller=new AbortController();getMarketRiskStatus(controller.signal).then(setData).catch(()=>{});return()=>controller.abort()},[])
  return <aside className="market-risk-banner" aria-label="大盘环境优先核查"><div><strong>先核对大盘环境</strong><span>{data?(data.status==='observed_snapshot'?`市场快照截至 ${data.requested_through}；当前风险尚未校准。`:'当前大盘数据未覆盖，不能由个股节点推断整体风险。'):'大盘数据尚未确认，当前风险未知。'}</span></div><Link to="/market">ETF、市场走势与流动性 <ArrowRight size={14}/></Link></aside>
}

export function MarketRiskPage(){
  const [data,setData]=useState<MarketRiskStatus|null>(null)
  const [error,setError]=useState('')
  const [loading,setLoading]=useState(true)
  const [window,setWindow]=useState(20)
  const [etfWindow,setETFWindow]=useState('5')
  const controller=useRef<AbortController|null>(null)
  const load=useCallback(async()=>{
    controller.current?.abort();const request=new AbortController();controller.current=request
    setLoading(true);setError('');setData(null)
    try{const result=await getMarketRiskStatus(request.signal);if(!request.signal.aborted)setData(result)}
    catch{if(!request.signal.aborted)setError('暂时无法读取市场环境。缺失数据不能视为低风险。')}
    finally{if(!request.signal.aborted)setLoading(false)}
  },[])
  useEffect(()=>{void load();return()=>controller.current?.abort()},[load])
  return <div className="learning-page market-risk-page">
    <header className="learning-header"><div><p className="eyebrow">研究工作台 / 大盘环境</p><h1>先看市场，再看节点</h1><p>ETF份额、市场走势、涨跌分布与流动性分别核对。大盘风险独立展示，个股事件不覆盖它。</p></div><button className="learning-refresh" disabled={loading} onClick={()=>void load()}><RefreshCw size={16}/>{loading?'读取中…':'重新核对'}</button></header>
    {loading&&<p role="status" className="learning-loading">正在读取市场快照和数据截止日…</p>}
    {error&&<p role="alert" className="experience-error">{error}</p>}
    {data&&<>
      <section className="market-risk-assessment" aria-label="当前风险可用性"><span>当前大盘风险</span><h2>{data.status==='observed_snapshot'?'已有快照，风险等级待校准':'当前无法确认'}</h2><p>{data.status==='observed_snapshot'?`完整收盘日目标 ${data.requested_through}；观察日 ${data.observation_date}。快照日期不代表数据已经覆盖观察日。`:`观察日 ${data.observation_date}。当前没有通过校验的市场快照，以下历史数值只用于核对计算。`}</p>{data.last_attempt?.status==='failed'&&<p className="market-risk-failure">最近更新失败：{data.last_attempt.reason==='provider_token_expired'?'行情接口凭证已过期':data.last_attempt.reason}；请求截至 {data.last_attempt.requested_through}。</p>}</section>
      <section className="market-risk-order" aria-label="研究顺序"><span>01 大盘环境</span><ArrowRight size={15}/><span>02 ST与小盘风格</span><ArrowRight size={15}/><span>03 个股节点与自身风险</span></section>
      <section aria-label="市场趋势与回撤"><header className="learning-section-head"><div><p className="eyebrow">方向 / 风格 / 流动性</p><h2>同一窗口，分开看市场与ST</h2></div><div className="market-risk-windows" aria-label="图表窗口">{[5,20,60].map(value=><button key={value} aria-pressed={window===value} onClick={()=>setWindow(value)}>{value}日</button>)}</div></header>
        <div className="market-risk-legend">{data.indices.map((index,i)=><span key={index.code}><i className={`market-line-${i%3}`}/>{index.name} · 截至 {index.through||'未知'}{index.historical_only?' · 历史快照':''}</span>)}</div>
        {data.indices.length>0?<><Paths indices={data.indices} window={window}/><p className="learning-footnote">起点归一为100；仅绘制所选窗口完整的序列。数据不足时保留缺口；ST等权仅消费覆盖率至少95%的日期。</p><div className="learning-table-wrap"><table className="learning-table market-risk-table"><thead><tr><th scope="col">市场基准</th><th scope="col">5日</th><th scope="col">20日</th><th scope="col">60日</th><th scope="col">60日最大回撤</th><th scope="col">5/20日成交额均值比</th></tr></thead><tbody>{data.indices.map(index=><tr key={index.code}><th scope="row">{index.name}<small>{index.through}</small></th><td>{pct(index.return_5d_pct)}</td><td>{pct(index.return_20d_pct)}</td><td>{pct(index.return_60d_pct)}</td><td>{pct(index.max_drawdown_60d_pct)}</td><td>{index.amount_5d_to_20d_ratio==null?'—':`${index.amount_5d_to_20d_ratio.toFixed(2)} 倍`}</td></tr>)}</tbody></table></div></>:<p className="learning-empty">市场基准缺失，无法计算趋势和回撤。</p>}
      </section>

      <section className="learning-freshness" aria-label="ETF份额与申赎"><header className="learning-section-head"><div><p className="eyebrow">资金撤离线索 / ETF样本</p><h2>份额变化与净申赎估算</h2></div><label>ETF观察窗口 <select aria-label="ETF观察窗口" value={etfWindow} onChange={event=>setETFWindow(event.target.value)}>{[1,5,20].map(value=><option key={value} value={String(value)}>{value}个交易日</option>)}</select></label></header>
        <p>固定观察8只沪深300、中证500和中证1000ETF。样本覆盖 {data.etf_aggregate[etfWindow]?.observed_etfs??0}/8；不外推全体ETF或机构持仓。净申赎金额需先排除份额折算等事件，当前尚未发布。</p>
        <div className="learning-table-wrap"><table className="learning-table"><thead><tr><th scope="col">ETF代码 / 跟踪组</th><th scope="col">份额变化</th><th scope="col">净申赎金额估算</th><th scope="col">核验状态</th></tr></thead><tbody>{Object.entries(data.parameters.etf_basket).map(([code,group])=>{const item=data.etfs.find(etf=>etf.code===code);const metric=item?.windows[etfWindow];return <tr key={code}><th scope="row">{code}<small>{group} · 截至 {item?.through||'未取得'}</small></th><td>{pct(metric?.share_change_pct)}</td><td>{amount(metric?.estimated_net_subscription_yuan)}</td><td>{metric?.status==='estimated'?'名义估算，不能识别资金身份':metric?.status==='corporate_actions_unchecked'?'份额事件未核验':'缺少同窗份额或净值'}{metric?.share_change_notional_yuan!=null&&<details><summary>未经份额事件校正的名义额</summary><p>{amount(metric.share_change_notional_yuan)}；不得当作已确认净申赎。</p></details>}</td></tr>})}</tbody></table></div>
      </section>

      <section className="learning-freshness" aria-label="市场宽度"><header className="learning-section-head"><div><p className="eyebrow">市场宽度</p><h2>风险是否在同步扩散</h2></div><span>{data.breadth.through||'截止日未取得'}</span></header>{data.breadth.status==='observed'?<><div className="market-breadth"><div><span>有收益记录</span><strong>{number(data.breadth.observed_trading_stocks)}</strong></div><div><span>上涨 / 下跌</span><strong>{number(data.breadth.advancing)} / {number(data.breadth.declining)}</strong></div><div><span>跌幅至少5%</span><strong>{number(data.breadth.declining_5pct_or_more)}</strong></div><div><span>收益中位数</span><strong>{pct(data.breadth.median_return_pct)}</strong></div></div><p>{data.breadth.scope}。成交额 {amount(data.breadth.amount_yuan)}。</p></>:<p className="learning-empty">当日涨跌分布尚未取得，无法判断同步下跌的范围。</p>}</section>

      <section className="learning-freshness market-risk-limits" aria-label="参数与检验边界"><h2>这组参数怎样进入研究</h2><p>先描述大盘环境，再比较ST风格与个股节点。当前参数版本 {data.parameter_version}；尚不设置资金撤退概率、风险权重或交易阈值。</p><ul>{data.limitations.map(limit=><li key={limit}>{limit}</li>)}</ul><p>下一步比较“仅节点”与“节点＋市场环境”，固定样本、同一观察时点和交易日窗口；最近两月只作压力案例，另设独立时段检验，避免按已知结果调权重。</p><div className="market-risk-sources">{data.sources.map(source=><a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a>)}</div></section>
      <footer className="learning-footer">页面重新核对只读取本地快照。当前数据不可用时保留未知，不发布“低风险”或“大资金撤退”的结论。</footer>
    </>}
  </div>
}
