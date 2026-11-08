import {STMembershipAudit} from './STMembershipAudit'
import {STLabelChanges} from './STLabelChanges'
import {useEffect,useState} from 'react'
import {ReadingChart} from './ReadingChart'
import {STRegimeThemes} from './STRegimeThemes'
import {STSampleIntegrity} from './STSampleIntegrity'
import {STMemberTransitions} from './STMemberTransitions'
import {STIndexCrosscheck} from './STIndexCrosscheck'
import {STMemberEntries} from './STMemberEntries'
import type {ReadingSeries} from './readingTypes'
import type {RegimeComparison,RegimeFixed,RegimePeriod,STRegimeData} from './stRegimeTypes'
import './stRegime.css'

const pct=(value:number|null|undefined)=>value==null?'待核':`${value>0?'+':''}${value.toFixed(2)}%`
const number=(value:number|null|undefined,digits=2)=>value==null?'待核':value.toFixed(digits)
const windows=['40','20','all']

function ComparisonTable({before,after}:{before:RegimePeriod;after:RegimePeriod}){
  const metrics:[string,keyof RegimePeriod,string][]=[['ST等权参考变化','reference_change_pct','%'],['中证全指同期','market_change_pct','%'],['中证2000同期','small_cap_change_pct','%'],['ST参考日波动','daily_volatility_pct','%'],['平均每日上涨家数占比','mean_positive_breadth_pct','%'],['每日个股P90−P10差距','mean_dispersion_pp','个百分点'],['跌破旧5%价格边界','beyond_old_down_pct','%'],['涨过旧5%价格边界','beyond_old_up_pct','%']]
  return <div className="regime-scroll" role="region" aria-label="前后窗口比较表" tabIndex={0}><table className="regime-table"><thead><tr><th scope="col">同口径比较</th><th scope="col">规则前 · {before.days}日<small>{before.start} — {before.through}</small></th><th scope="col">规则后 · {after.days}日<small>{after.start} — {after.through}</small></th></tr></thead><tbody>{metrics.map(([title,key,unit])=><tr key={key}><th scope="row">{title}</th>{[before,after].map((period,i)=><td key={i}>{number(period[key] as number|null)}<small className="regime-unit">{unit}</small></td>)}</tr>)}</tbody></table></div>
}

function Scatter({data,comparison}:{data:STRegimeData;comparison:RegimeComparison}){
  const rows=data.daily.filter(r=>r.date>=comparison.before.start&&r.date<=comparison.after.through)
  const max=Math.max(1,...rows.flatMap(r=>[Math.abs(r.market_pct),Math.abs(r.return_pct)]))*1.15
  const x=(v:number)=>300+v/max*240,y=(v:number)=>180-v/max*140
  return <figure className="regime-scatter"><svg viewBox="0 0 600 370" role="img" aria-label="ST与大盘逐日涨跌散点，规则前后对照"><title>每点一个交易日，横轴中证全指，纵轴ST等权参考；相关性不是因果贡献</title><line x1="60" x2="540" y1="180" y2="180"/><line x1="300" x2="300" y1="40" y2="320"/>{[-max,0,max].map(v=><g key={v}><text x={x(v)} y="344" textAnchor="middle">{v.toFixed(1)}%</text>{v!==0&&<text x="48" y={y(v)+5} textAnchor="end">{v.toFixed(1)}%</text>}</g>)}<text x="310" y="24">ST等权参考 ↑</text><text x="590" y="365" textAnchor="end">中证全指 →</text>{rows.map(r=><circle key={r.date} cx={x(r.market_pct)} cy={y(r.return_pct)} r="4.3" className={r.date<data.rule_day?'regime-pre':'regime-post'}><title>{r.date} · 中证全指 {pct(r.market_pct)} · ST {pct(r.return_pct)}</title></circle>)}</svg><figcaption><span className="regime-pre-label">● 规则前</span><span className="regime-post-label">● 规则后</span> 一点一天；同向、反向和弱联动的日子都保留。</figcaption></figure>
}

const bins=[{label:'低于−20%',test:(v:number)=>v< -20},{label:'−20%至−10%',test:(v:number)=>v>= -20&&v< -10},{label:'−10%至0%',test:(v:number)=>v>= -10&&v<0},{label:'0%至10%',test:(v:number)=>v>=0&&v<10},{label:'10%至20%',test:(v:number)=>v>=10&&v<20},{label:'20%及以上',test:(v:number)=>v>=20}]
function Distribution({data}:{data:RegimeFixed}){
  const counts=bins.map(bin=>data.rows.filter(row=>row.return_pct!=null&&bin.test(row.return_pct)).length)
  const max=Math.max(1,...counts)
  return <div className="regime-distribution" role="img" aria-label={`固定名单收益分布：${data.covered}只有端点，${data.missing}只未计算`}>
    {bins.map((bin,index)=><div className="regime-bin" key={bin.label}><span>{bin.label}</span><div><i style={{width:`${counts[index]/max*100}%`}}/></div><b>{counts[index]}只</b></div>)}
    <p className="reading-caption">另外 {data.missing} 只没有可比端点或仍需核价，保留在明细中。分布只描述有完整起止端点的 {data.covered} 只。</p>
  </div>
}

function StockTable({comparison}:{comparison:RegimeComparison}){
  const [query,setQuery]=useState('')
  const [scope,setScope]=useState('all')
  const before=new Map(comparison.fixed_before.rows.map(row=>[row.symbol,row]))
  const rows=comparison.fixed_after.rows.filter(row=>(!query||`${row.name} ${row.symbol}`.toLowerCase().includes(query.toLowerCase()))&&(scope==='all'||scope==='missing'&&row.return_pct==null||scope==='left'&&!row.still_st_at_end||scope===row.venue))
  return <>
    <div className="regime-stock-controls"><label>查找公司<input type="search" aria-label="横向复盘查找公司" value={query} onChange={e=>setQuery(e.target.value)} placeholder="名称或代码"/></label><label>名单范围<select aria-label="横向复盘名单范围" value={scope} onChange={e=>setScope(e.target.value)}><option value="all">全部{comparison.fixed_after.total}只，按代码排列</option><option value="上海">上海主板</option><option value="深圳">深圳主板</option><option value="missing">端点或复权待核</option><option value="left">期末不再在ST名单中</option></select></label><span>{rows.length}只</span></div>
    <div className="regime-scroll" role="region" aria-label="固定名单全部个股表现" tabIndex={0}><table className="regime-table regime-stock-table"><thead><tr><th scope="col">7月3日名单</th><th scope="col">规则前端点变化</th><th scope="col">规则后端点变化</th><th scope="col">规则后较大盘</th><th scope="col">完整性与名单变化</th></tr></thead><tbody>{rows.map(row=><tr key={row.symbol}><th scope="row">{row.name}<small>{row.symbol} · {row.venue}</small></th><td>{pct(before.get(row.symbol)?.return_pct)}</td><td>{pct(row.return_pct)}</td><td>{row.market_excess_pp==null?'待核':`${number(row.market_excess_pp)}个百分点`}</td><td><details><summary>{row.sample_note?'缺口原因已核':row.gap?'端点待核':row.missing_quote_days?'端点齐，路径有缺口':'端点与路径齐'}{!row.still_st_at_end?' · 已离开ST名单':''}</summary><p>{row.sample_note?row.sample_note.explanation:row.gap||'前复权起止价格变化，不能认证实际成交收益。'}窗口内缺报价 {row.missing_quote_days} 日；与日涨跌幅可比 {row.consistency_days} 日，不一致 {row.consistency_mismatches} 日。</p>{before.get(row.symbol)?.gap&&<p>规则前：{before.get(row.symbol)?.gap}</p>}<p>{row.sample_note?row.sample_note.boundary:'名单移出可能涉及摘帽、退市或其他状态变化，本表不猜原因。'}</p></details></td></tr>)}</tbody></table>{rows.length===0&&<p>没有符合筛选的公司。</p>}</div>
  </>
}

export function STRegimeSection(){
  const [data,setData]=useState<STRegimeData|null>(null)
  const [error,setError]=useState('')
  const [request,setRequest]=useState(0)
  const [busy,setBusy]=useState(true)
  const [windowKey,setWindowKey]=useState('all')
  const [view,setView]=useState('规则前后')
  const [chartScope,setChartScope]=useState('after')
  const [ruleSelected,setRuleSelected]=useState(false)
  const [evidenceOpen,setEvidenceOpen]=useState(false)
  useEffect(()=>{
    const controller=new AbortController()
    async function read(){
      setBusy(true)
      try{
        const response=await fetch('/api/v1/workbench/st-regime',{signal:controller.signal,cache:'no-store'})
        if(!response.ok)throw new Error('横向复盘暂时读取失败')
        const packet=await response.json()
        if(packet.availability!=='available'||!Array.isArray(packet.data?.comparisons)||packet.data.comparisons.length===0)throw new Error(packet.data?.message||'横向复盘快照尚不可用')
        if(!controller.signal.aborted){setData(packet.data);setError('')}
      }catch(reason){if(!controller.signal.aborted){setData(null);setError(reason instanceof Error?reason.message:'横向复盘读取失败')}}
      finally{if(!controller.signal.aborted)setBusy(false)}
    }
    void read()
    const focus=()=>{if(document.visibilityState!=='hidden')void read()}
    window.addEventListener('focus',focus)
    return()=>{controller.abort();window.removeEventListener('focus',focus)}
  },[request])
  const comparison=data?.comparisons.find(row=>row.key===windowKey)??data?.comparisons[0]
  const after=comparison?.after,before=comparison?.before,fixed=comparison?.fixed_after
  let series:ReadingSeries[]=[]
  if(data&&comparison){
    const period=chartScope==='before'?comparison.before:comparison.after
    const start=data.daily.find(row=>row.date===period.start)?.anchor
    const path=data.path.filter(row=>chartScope==='all'||start!=null&&row.date>=start&&row.date<=period.through)
    series=([['st','主板ST等权参考'],['market','中证全指'],['small','中证2000']] as const).map(([key,name])=>({key,name,points:path.map(row=>({date:row.date,value:row[key],level:row[key]/path[0][key]*100})),change_pct:(path.at(-1)![key]/path[0][key]-1)*100}))
  }
  return <section id="st-cross-section" className="regime-section" aria-label="ST横向制度复盘">
    <header className="regime-head"><div><p className="reading-kicker">按问题看复盘</p><h2>横向看ST</h2></div><button type="button" disabled={busy} onClick={()=>setRequest(n=>n+1)}>{busy?'读取中…':'重读已核快照'}</button></header>
    {error&&<p role="alert">{error}。已有个股复盘仍可在下方查看。</p>}
    {!data&&!error&&<p role="status">正在读取整批ST的同窗比较…</p>}
    {data&&comparison&&after&&before&&fixed&&<>
      <STRegimeThemes data={data} comparison={comparison} onEvidence={(nextView,targetId)=>{setView(nextView);setEvidenceOpen(true);if(targetId&&['st-member-entries','st-member-transitions','st-sample-integrity','st-label-changes','st-membership-audit'].includes(targetId))setWindowKey('all');requestAnimationFrame(()=>document.getElementById(targetId??'st-evidence')?.scrollIntoView?.({behavior:'smooth',block:'start'}))}} chart={<figure className="regime-story-figure"><figcaption><strong>这段行情，放回市场里看</strong><span>{comparison.after.start} — {comparison.after.through}，从前一交易日收盘起算</span></figcaption><ReadingChart key={`story-${windowKey}`} series={(['st','market','small'] as const).map((key,index)=>{const start=data.daily.find(row=>row.date===comparison.after.start)?.anchor;const path=data.path.filter(row=>start!=null&&row.date>=start&&row.date<=comparison.after.through);return {key,name:['主板ST等权参考','中证全指','中证2000'][index],points:path.map(row=>({date:row.date,value:row[key],level:row[key]/path[0][key]*100})),change_pct:(path.at(-1)![key]/path[0][key]-1)*100}})} label="ST与市场同期走势"/><p className="reading-caption">三线从同一天归零，比较路径；ST线是每日在场股票的等权参考，不是固定持仓回报。</p></figure>}/>
      <details id="st-evidence" className="regime-evidence" open={evidenceOpen} onToggle={event=>setEvidenceOpen(event.currentTarget.open)}><summary><span>数据、图表与全部样本</span><small>切换观察窗口，核对计算与原始来源</small></summary>
      <p className="regime-boundary"><strong>完整横截面截至 {data.through}</strong> · 7月6日生效；主板A股ST/*ST；创业板、科创板及北交所不混入。</p>
      <div className="regime-controls"><div className="regime-tabs" role="group" aria-label="横向复盘视角">{['规则前后','大盘联动','整批个股'].map(label=><button key={label} aria-pressed={view===label} onClick={()=>setView(label)}>{label}</button>)}</div><label>比较窗口<select aria-label="ST前后比较窗口" value={windowKey} onChange={e=>setWindowKey(e.target.value)}>{windows.map(key=>{const option=data.comparisons.find(c=>c.key===key);return option?<option key={key} value={key}>{option.label}</option>:null})}</select></label></div>
      <div className="regime-verdict"><h3>{(after.reference_change_pct??0)<-2?'整体参考下跌，本窗没有出现普涨':Math.abs(after.reference_change_pct??0)<=2?'整体接近持平，个股涨跌仍明显分化':'整体参考上涨，仍需核对上涨覆盖面'}</h3><p>规则后 {after.days} 个交易日，ST等权参考 {pct(after.reference_change_pct)}，中证全指 {pct(after.market_change_pct)}。7月3日固定名单中，有端点的 {fixed.covered}/{fixed.total} 只，收益中位数 {pct(fixed.median_pct)}；{number(fixed.positive_pct,1)}% 上涨。</p>{windowKey==='all'&&<p>本项前窗40日、后窗{after.days}日，时长不同；精确前后比较请切换20日或40日。</p>}</div>
      {view==='规则前后'&&<>
        <div className="regime-chart-head"><h3>把ST放回市场里看</h3><label>曲线范围<select aria-label="ST横向曲线范围" value={chartScope} onChange={e=>setChartScope(e.target.value)}><option value="all">完整覆盖 · 标出规则生效</option><option value="before">仅规则前窗口 · 从0%起</option><option value="after">仅规则后窗口 · 从0%起</option></select></label></div>
        <p className="reading-caption">曲线从 {series[0]?.points[0]?.date} 收盘起算，至 {series[0]?.points.at(-1)?.date}；三线同起点归零。{chartScope==='all'?'完整覆盖期与上方所选前后窗口分别读数。':'与上方所选窗口对应。'}</p>
        <ReadingChart key={`${windowKey}-${chartScope}`} series={series} label="主板ST、全市场与小盘风格同期路径" eventMarkers={chartScope==='all'?[{date:data.rule_day,id:'rule',label:'2026年7月6日：主板ST涨跌幅5%改10%正式生效',selected:ruleSelected,count:1}]:[]} onEventMarker={()=>setRuleSelected(v=>!v)}/>
        {ruleSelected&&chartScope==='all'&&<p className="regime-rule-note">7月6日正式生效，4月24日已经公布。变化前可能已有预期交易，曲线断点不能单独认证制度因果。<a href={data.sources[0].url} target="_blank" rel="noreferrer">查看交易所说明 ↗</a></p>}
        <ComparisonTable before={before} after={after}/>
        <p className="reading-caption">“日波动”是ST等权参考日收益的总体标准差。“上涨占比”先逐日计算、再按日平均；突破旧边界以证券—交易日为分母，按前收盘价与分币舍入逐条判断，不是涨跌停统计。每日P90−P10衡量横向分化，与整批路径波动不同。</p>
      </>}
      {view==='大盘联动'&&<>
        <STIndexCrosscheck data={data.themes?.index_crosscheck}/>
        <div className="regime-market-layout"><div><h3>{Math.abs(after.relation.correlation??0)>Math.abs(before.relation.correlation??0)?'规则后，本窗ST与大盘同日联动更强':'本窗前后联动不同，保留反向与弱联动日'}</h3><p>本窗口相关系数由 {number(before.relation.correlation)} 变为 {number(after.relation.correlation)}。这是同日联动描述；不能据此把跌幅分摊给大盘，或把变化归因于规则。</p><p>大盘下跌日，规则后ST平均 {pct(after.conditions.find(c=>c.key==='down')?.st_mean_pct)}；其中跌超1%的日子只有 {after.conditions.find(c=>c.key==='stress')?.days} 天，样本有限。</p><p className="reading-caption">中证2000同时保留在主图，帮助识别小盘风格。上市公司事件、成员变化和市场环境仍可能共同作用。</p></div><Scatter data={data} comparison={comparison}/></div>
        <div className="regime-scroll" role="region" aria-label="不同大盘环境下的ST表现" tabIndex={0}><table className="regime-table"><thead><tr><th scope="col">市场环境</th><th scope="col">时期</th><th scope="col">天数</th><th scope="col">大盘日均</th><th scope="col">ST日均</th><th scope="col">每日上涨占比均值</th></tr></thead><tbody>{before.conditions.flatMap((condition,index)=>[before,after].map((period,phase)=>{const c=period.conditions[index];return <tr key={`${condition.key}-${phase}`}><th scope="row">{condition.label}</th><td>{phase===0?'规则前':'规则后'}</td><td>{c.days}</td><td>{pct(c.market_mean_pct)}</td><td>{pct(c.st_mean_pct)}</td><td>{pct(c.positive_breadth_pct)}</td></tr>}))}</tbody></table></div>
      </>}
      {view==='整批个股'&&<>
        <div className="regime-distribution-layout"><div><h3>固定7月3日的{fixed.total}只，看看谁被平均数遮住</h3><p>规则后端点分布：P10 {pct(fixed.p10_pct)}，中位数 {pct(fixed.median_pct)}，P90 {pct(fixed.p90_pct)}。{fixed.missing} 只未纳入端点分布，仍保留在表中。</p><p>两边均有完整端点的同一批 {comparison.paired.count} 只：前窗中位数 {pct(comparison.paired.before_median_pct)}，后窗 {pct(comparison.paired.after_median_pct)}。这是覆盖子样本的核对，不能代表全部幸存与退出者。</p></div><Distribution data={fixed}/></div>
        <p className="reading-caption">{fixed.note}</p>{windowKey==='all'&&<><STMembershipAudit data={data.themes?.membership_audit}/><STLabelChanges data={data.themes?.label_changes}/></>}{windowKey==='all'&&<STMemberEntries data={data.themes?.member_entries}/>}
        {windowKey==='all'&&<STMemberTransitions data={data.themes?.member_transitions}/>}
        {windowKey==='all'&&<STSampleIntegrity data={data.themes?.sample_integrity} total={fixed.total} covered={fixed.covered}/>}<StockTable comparison={comparison}/>
      </>}

      <details className="regime-audit"><summary>名单、分母、来源和更新限制</summary><p>7月3日主板名单 {data.universe.anchor_members} 只，期末 {data.universe.endpoint_members} 只，整个覆盖期曾入选 {data.universe.distinct_main_board_members} 只。期末相较7月3日新增 {data.universe.entrants.length} 只、移出 {data.universe.exits.length} 只；{data.themes?.member_transitions?data.themes?.member_entries?'新增与移出边界见上方原件核对，全部每日状态仍待扩大核验。':'移出原因和边界见上方原件核对，新增原因仍待逐一核实。':'移出原因尚未逐一核验。'}</p><p>前窗 {before.trading_observations}/{before.member_observations} 个成员日有成交，停牌 {before.suspended_observations}；后窗 {after.trading_observations}/{after.member_observations} 个成员日有成交，停牌 {after.suspended_observations}。未解析缺失：前 {before.missing_observations}、后 {after.missing_observations}；不是把停牌当平盘。</p><ul>{data.limitations.map(note=><li key={note}>{note}</li>)}</ul><div className="regime-source-links">{data.sources.map(source=><a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a>)}</div><p className="reading-caption">生成于 {new Date(data.generated_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}；数据标识 {data.content_digest.slice(0,12)}。重读快照不会采集新行情；新数据需核验、重算后发布。</p></details>
      </details>
    </>}
  </section>
}
