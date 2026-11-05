import {ArrowRight, CircleAlert, RefreshCw} from 'lucide-react'
import {useCallback, useEffect, useRef, useState} from 'react'
import {Link} from 'react-router-dom'
import {getLearningStatus} from './api'
import type {ExperienceStatus, LearningMethod, LearningStatus, RegressionState} from './types'
import './learning.css'

const STATE_LABEL:Record<RegressionState,string>={
  current:'本期规则通过',due:'已到复验期',never_checked:'尚未复验',needs_recheck:'版本需复验',
  unverified:'未能验证',failed:'复验失败',unknown:'记录不可读',
}
const STATUS_LABEL:Record<ExperienceStatus,string>={accepted:'已接受',candidate:'候选',blocked:'已阻断',ignored:'已忽略',merged:'已合并',closed:'已关闭',superseded:'已取代'}
const count=(value:number|null|undefined)=>value==null?'—':value.toLocaleString('zh-CN')
function time(value:string|null|undefined){
  if(!value)return '无记录'
  const parsed=new Date(value)
  return Number.isNaN(parsed.getTime())?'日期无效':parsed.toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})
}
function methodGap(method:LearningMethod){
  const reasons=[]
  if(method.validator_passed_source_runs==null)reasons.push('来源记录不可读')
  else if(method.validator_passed_source_runs<2)reasons.push(`有效来源 ${method.validator_passed_source_runs}/2`)
  if(method.unsupported_validation_refs.length)reasons.push(`${method.unsupported_validation_refs.length} 项验证尚未绑定可执行检查`)
  if(method.blocking_conflict)reasons.push('存在阻断冲突')
  return reasons.join('；')||'来源数量已达门槛；执行检查后才能决定晋级'
}

export function LearningPage(){
  const [data,setData]=useState<LearningStatus|null>(null)
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [query,setQuery]=useState('')
  const [filter,setFilter]=useState('active')
  const controller=useRef<AbortController|null>(null)
  const load=useCallback(async()=>{
    controller.current?.abort()
    const request=new AbortController()
    controller.current=request
    setLoading(true);setError('');setData(null)
    try{
      const result=await getLearningStatus(request.signal)
      if(!request.signal.aborted)setData(result)
    }catch{
      if(!request.signal.aborted)setError('暂时无法读取更新与复盘。请重试；未读到的库存不会显示为零。')
    }finally{if(!request.signal.aborted)setLoading(false)}
  },[])
  useEffect(()=>{void load();return()=>controller.current?.abort()},[load])
  const methods=data?.methods.filter(method=>
    (filter==='all'||(filter==='active'?['accepted','candidate','blocked'].includes(method.status):method.status===filter))
    &&`${method.title} ${method.experience_id}`.toLowerCase().includes(query.toLowerCase().trim()),
  )??[]
  const needsCheck=data?.regression_counts&&Object.entries(data.regression_counts)
    .filter(([key])=>key!=='current').reduce((sum,[,value])=>sum+value,0)
  return <div className="learning-page">
    <header className="learning-header">
      <div><p className="eyebrow">研究工作台 / 更新与复盘</p><h1>让改进有据可查</h1><p>从真实运行中总结方法，检查是否符合既定规则，再核对数据更新到哪里。</p></div>
      <button className="learning-refresh" onClick={()=>void load()} disabled={loading}><RefreshCw size={16}/>{loading?'读取中…':'重新核对'}</button>
    </header>
    {loading&&<p role="status" className="learning-loading">正在核对本地运行、经验、复验记录和数据清单…</p>}
    {error&&<p role="alert" className="experience-error">{error}</p>}
    {data&&<>
      <div className="learning-asof"><span>核对时间 {time(data.generated_at)} · 北京时间</span><span>每次打开或重新核对时读取本地记录</span></div>
      {data.gaps.length>0&&<p className="learning-notice" role="status"><CircleAlert size={18}/>部分来源缺失或不可读，相关数字显示为“—”。<span>{data.gaps.join(' · ')}</span></p>}
      <section className="learning-ledger" aria-label="改进闭环库存">
        <article><span>01 / 研究运行</span><strong>{count(data.runs?.total)}</strong><p>{count(data.runs?.validator_passed)} 条通过结构校验</p><Link to="/runs">追溯回答 <ArrowRight size={14}/></Link></article>
        <article><span>02 / 待沉淀方法</span><strong>{count(data.counts?.candidate)}</strong><p>{count(data.counts?.blocked)} 条方法被阻断</p><Link to="/">查看方法库 <ArrowRight size={14}/></Link></article>
        <article><span>03 / 已接受方法</span><strong>{count(data.counts?.accepted)}</strong><p>有接受记录，仍需定期复验</p><Link to="/#methods">查看经验 <ArrowRight size={14}/></Link></article>
        <article className="learning-verified"><span>04 / 本期规则检查通过</span><strong>{count(data.regression_counts?.current)}<small> / {count(data.counts?.accepted)}</small></strong><p>{needsCheck==null?'复验来源不可读':`${needsCheck} 条已接受方法需要核对`}</p><a href="#method-audit">查看逐条结果 <ArrowRight size={14}/></a></article>
      </section>
      <p className="learning-footnote">四项是各自的库存，统计单位不同。不能相除为转化率，也不能作为准确率。</p>

      <section className="learning-diagnosis" aria-label="自我提升与运行机制">
        <div><p className="eyebrow">自我提升</p><h2>效果尚未测量</h2><p>{data.quality_evaluation.reason}</p><p>{count(data.runs?.with_experience_hits)} 条运行记录过经验调用。调用表示使用过方法，不证明回答变好。</p></div>
        <div><p className="eyebrow">自我更新</p><h2>触发机制与实际运行分开看</h2><dl><div><dt>方法晋级</dt><dd>候选或反馈触发；至少 {data.automation.minimum_source_runs} 个有效来源运行，并通过回归、冲突与通用性检查。</dd></div><div><dt>定期复验</dt><dd>由维护流程显式执行。此页没有读取排程状态，不能据此判断定时任务正在运行。</dd></div><div><dt>原复验记录</dt><dd>{data.latest_regression?`${time(data.latest_regression.completed_at)}，检查 ${data.latest_regression.accepted_examined} 条方法。`:'尚无可读批次。'}{data.latest_regression?.accepted_examined===0&&' 空批次不能证明库存已验证。'}</dd></div>{data.readonly_audit?.availability==='current'&&<div><dt>最近只读复验</dt><dd>{time(data.readonly_audit.completed_at)}，检查 {data.readonly_audit.accepted_examined} 条；{data.readonly_audit.passed} 条规则通过，{data.readonly_audit.failed} 条失败，{data.readonly_audit.unverified} 条未验证。结果已绑定当前方法和代码；软件检查不代表研究效果。</dd></div>}</dl></div>
      </section>

      <section id="method-audit" className="learning-methods" aria-label="经验逐条核验">
        <header className="learning-section-head"><div><p className="eyebrow">经验总结</p><h2>每条方法的依据与状态</h2></div><Link to="/">进入经验中心 <ArrowRight size={14}/></Link></header>
        <div className="learning-filters"><label>查找方法<input type="search" value={query} onChange={event=>setQuery(event.target.value)} placeholder="方法标题或编号"/></label><label>状态<select value={filter} onChange={event=>setFilter(event.target.value)}><option value="active">在用与待验证</option><option value="accepted">已接受</option><option value="candidate">候选</option><option value="blocked">已阻断</option><option value="all">全部状态</option></select></label><span>{methods.length} 条</span></div>
        {data.counts===null?<p className="learning-empty">经验库不可读，无法核对方法。</p>:methods.length===0?<p className="learning-empty">没有符合筛选条件的方法。</p>:<div className="learning-table-wrap"><table className="learning-table"><thead><tr><th scope="col">方法</th><th scope="col">有效来源</th><th scope="col">定期复验</th><th scope="col">核对结果</th></tr></thead><tbody>{methods.map(method=><tr key={method.experience_id}><th scope="row"><strong>{method.title}</strong><span>{STATUS_LABEL[method.status]} · v{method.experience_version}</span><details><summary>审计出处</summary><p>{method.experience_id}</p><p>接受/审阅者：{method.reviewed_by||'无记录'}<br/>审阅：{time(method.reviewed_at)}</p><p>结果来源：{method.verification_source==='readonly_audit'?'只读复验':'原复验记录'}。</p><p>检查代码版本：{method.verification_binding?.software_digest.slice(0,12)||'未绑定'}；方法版本：{method.verification_binding?.method_digest.slice(0,12)||'未绑定'}。</p><p>来源引用 {method.source_ref_count} 个；本地存在 {count(method.existing_source_runs)} 个运行。未解析引用 {method.unresolved_source_refs?.length??'—'} 个。</p>{method.unresolved_source_refs?.map(ref=><code key={ref}>{ref}</code>)}</details></th><td>{count(method.validator_passed_source_runs)}<small>通过结构校验的不同运行</small></td><td><span className={`learning-state state-${method.regression_state}`}>{STATE_LABEL[method.regression_state]}</span><small>上次：{time(method.last_checked_at)}</small><small>到期：{time(method.next_due_at)}</small></td><td>{method.status==='accepted'?<>{method.regression_state==='current'?'本期规则检查通过；方法效果仍未测量。':method.regression_state==='failed'?'本轮软件规则检查未通过。':method.regression_state==='unverified'?'本轮规则未能完成验证。':'入库状态保留；尚无当前规则检查结果。'}{method.verification_notes?.map(note=><p key={note}>{note}</p>)}{method.unsupported_validation_refs.length>0&&!method.verification_notes?.length&&<p>存在尚未绑定的验证项。</p>}</>:methodGap(method)}</td></tr>)}</tbody></table></div>}
      </section>

      <section className="learning-freshness" aria-label="数据更新时点">
        <header className="learning-section-head"><div><p className="eyebrow">自我更新 / 数据</p><h2>清单合格到哪一天</h2></div><span>观察日 {data.observation_date}</span></header>
        <p>清单中的 current / ready 只针对当时声明的目标。下列“距观察日”按自然日计算，不判断交易日缺口；冻结方法库也不要求每天更新。</p>
        {data.freshness.availability!=='available'?<p className="learning-empty">数据清单不可读，无法确认更新时点。</p>:<><div className="learning-table-wrap"><table className="learning-table"><thead><tr><th scope="col">来源</th><th scope="col">数据/核查截止</th><th scope="col">距观察日</th><th scope="col">清单当时状态</th></tr></thead><tbody>{data.freshness.sources.map(source=><tr key={source.source_id}><th scope="row">{source.label}<details><summary>来源与范围</summary><code>{source.source_ref}</code><p>记录 {count(source.row_count)}；覆盖数 {count(source.coverage_count)}。各来源单位由原清单定义。</p><p>检查日期：{source.checked_at||'未提供'}；声明目标：{source.expected_through||'未声明'}。</p></details></th><td>{source.as_of||'未提供'}</td><td>{source.age_calendar_days==null?'无法计算':source.age_calendar_days<0?'日期晚于观察日':`${source.age_calendar_days} 天`}</td><td>{source.declared_status}</td></tr>)}</tbody></table></div><details className="learning-manifest"><summary>查看本次清单标识与已声明缺口</summary><p>{data.freshness.manifest_id} · 生成于 {time(data.freshness.generated_at)}</p><p>范围：{count(data.freshness.research_symbol_count)} 只研究标的；成员快照 {data.freshness.universe_as_of||'未提供'}。</p>{[...(data.freshness.blocking_gaps??[]),...(data.freshness.coverage_gaps??[])].map((gap,index)=><p key={index}>{gap}</p>)}</details></>}
      </section>
      {data.market_updates&&<section className="learning-freshness" aria-label="市场来源更新"><header className="learning-section-head"><div><p className="eyebrow">自我更新 / 新接入来源</p><h2>市场数据各自更新到哪里</h2></div><Link to="/market">查看大盘环境 <ArrowRight size={14}/></Link></header><p>这些快照与上方个股价格、公告清单分别维护。新市场数据到位，不代表旧研究数据已经同步，也不证明定时更新已运行。</p><div className="learning-table-wrap" role="region" aria-label="可滚动的市场来源更新表" tabIndex={0}><table className="learning-table"><thead><tr><th scope="col">官方来源</th><th scope="col">实际截止</th><th scope="col">记录与目标覆盖</th><th scope="col">核查状态</th></tr></thead><tbody>{data.market_updates.map(source=><tr key={source.source_id}><th scope="row"><a href={source.url} target="_blank" rel="noreferrer">{source.label} ↗</a><details><summary>采集与范围</summary><p>{source.date_basis==='current_list_observation'?`名单读取日 ${source.observation_date||'未取得'}`:`目标截止 ${source.requested_through||'未取得'}`}；采集 {time(source.fetched_at)}。</p><code>{source.snapshot_digest||'无已核对快照'}</code></details></th><td>{source.date_basis==='current_list_observation'?`读取于 ${source.observation_date||'未取得'}`:<>{source.date_basis==='catalog_search_cutoff'?'检索至 ':source.date_basis==='historical_price_archive'?'价格记录窗 ':source.date_basis==='historical_notice_review'?'公告核对窗 ':''}{source.observed_through_min||'未取得'}</>}{source.observed_through_max&&source.observed_through_max!==source.observed_through_min?` 至 ${source.observed_through_max}`:''}</td><td>{count(source.observation_count)} {source.observation_unit||'条'}<small>{source.date_basis==='current_list_observation'?`本次读取 ${count(source.observed_source_groups)}/${source.declared_series} 张分类表`:source.coverage_basis==='missing_day_episodes'?`完整区间 ${count(source.observed_source_groups)}/${count(source.declared_series)} 组`:source.coverage_basis==='price_archives'?`价格原件 ${count(source.observed_source_groups)}/${count(source.declared_series)} 只证券`:`目标日期覆盖 ${count(source.series_at_target)}/${source.declared_series} ${source.coverage_unit||'条序列'}`}</small></td><td>{source.availability==='observed'?'快照已核对':source.availability==='partial'?'已核对部分依据':source.availability==='invalid'?'快照校验未通过':'未取得快照'}<small>{source.note}</small></td></tr>)}</tbody></table></div></section>}
      {data.conflicts.length>0&&<section className="learning-conflicts" aria-label="方法冲突"><h2>冲突检查</h2>{data.conflicts.map(conflict=><p key={conflict.conflict_id}>{conflict.severity==='blocking'?'阻断':'需核对'}：{conflict.detail}</p>)}</section>}
      <footer className="learning-footer">此页只读取记录。重新核对不会更新行情、执行复验或接受方法。经验始终是方法提示，每次研究仍需新的事实依据。</footer>
    </>}
  </div>
}
