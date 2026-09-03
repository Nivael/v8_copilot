import {useEffect,useState} from 'react'
import {AlertTriangle,ArrowUpRight,CalendarDays,CircleDot,FileText,RefreshCw,ScanSearch} from 'lucide-react'
import {getDailyIntelligence} from './api'
import type {DailyIntelligence} from './types'

function text(value:unknown,fallback='—'){return typeof value==='string'||typeof value==='number'?String(value):fallback}
function list(value:unknown){return Array.isArray(value)?value.map(String):[]}
function pct(value:unknown){return typeof value==='number'?`${value>0?'+':''}${value.toFixed(2)}%`:'—'}
function nested(value:unknown,key:string){return value&&typeof value==='object'?text((value as Record<string,unknown>)[key]):'—'}

function Status({value}:{value:string}){
  const label=value==='descriptive'?'可读事实':value==='shadow'?'影子观察':'暂不可用'
  return <span className={`daily-status ${value}`}>{label}</span>
}

export function DailyIntelligencePage(){
  const [payload,setPayload]=useState<DailyIntelligence|null>(null)
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(true)
  const load=()=>{setBusy(true);setError('');getDailyIntelligence().then(setPayload).catch(()=>setError('每日数据尚未准备好，请先完成维护运行。')).finally(()=>setBusy(false))}
  useEffect(load,[])
  if(busy)return <div className="daily-page daily-loading"><RefreshCw className="spin"/>正在汇总正式公告与活动事实…</div>
  if(error||!payload)return <div className="daily-page"><div className="daily-empty"><AlertTriangle/><h1>每日观察暂不可用</h1><p>{error}</p><button onClick={load}>重新读取</button></div></div>
  return <div className="daily-page">
    <header className="daily-hero"><div><p className="eyebrow">P7 DAILY INTELLIGENCE · {payload.as_of}</p><h1>今天先查什么</h1><p>正式公告、异常交易活跃和证据缺口分开计算，再连接成研究顺序。</p></div><div className="daily-release"><div><small>公告</small><Status value={payload.release_status.p7a_announcements}/></div><div><small>量价</small><Status value={payload.release_status.p7b_activity}/></div><div><small>联动</small><Status value={payload.release_status.p7c_linkage}/></div></div></header>
    <section className="daily-risk"><AlertTriangle size={18}/><span>{payload.risk_notice}</span></section>
    <section className="daily-coverage"><div><small>当日 ST 成员</small><strong>{payload.coverage.membership_count}</strong></div><div><small>活动事实</small><strong>{payload.coverage.activity_row_count}</strong></div><div><small>自由流通换手覆盖</small><strong>{(payload.coverage.turnover_rate_f_coverage*100).toFixed(1)}%</strong></div><div><small>全体榜门</small><strong>{payload.coverage.full_universe_ready?'通过':'未通过'}</strong></div></section>

    <section className="daily-section"><header><span>01</span><div><h2>硬状态变化</h2><p>只认受理、批准、签约、控制权完成、摘帽/退市决定等真正跃迁。</p></div></header><div className="daily-grid">{payload.hard_transitions.length?payload.hard_transitions.map((item,index)=><article key={text(item.transition_id,String(index))}><CircleDot/><div><strong>{text(item.symbol)} · {text(item.event_type)}</strong><p>{text(item.from_state)} → {text(item.to_state)}</p><small>{text(item.available_as_of)} · {text(item.evidence_status)}</small></div></article>):<p className="daily-none">当日未记录硬状态跃迁。</p>}</div></section>

    <section className="daily-section"><header><span>02</span><div><h2>重点公告</h2><p>“重点”只表示会改变研究判断，不表示利好或利空。</p></div></header><div className="daily-stack">{payload.priority_announcements.length?payload.priority_announcements.map((item,index)=><article key={text(item.bundle_id,String(index))}><div className="daily-symbol">{text(item.symbol)}</div><div><strong>{list(item.titles)[0]||'公告证据包'}</strong><p>{list(item.priority_reasons).join(' · ')}</p><small>{list(item.announcement_ids).length} 份同主题材料 · {text(item.conflict_status)}</small></div>{list(item.source_urls)[0]&&<a href={list(item.source_urls)[0]} target="_blank" rel="noreferrer" aria-label="打开正式公告"><ArrowUpRight size={17}/></a>}</article>):<p className="daily-none">当日没有进入重点区的正式公告。</p>}</div></section>

    <section className="daily-section"><header><span>03</span><div><h2>异常交易活跃</h2><p>只展示预注册 balanced 命中，当前仍处于 shadow。</p></div></header><div className="daily-stack">{payload.activity_anomalies.length?payload.activity_anomalies.map((item,index)=><article key={text(item.anomaly_id,String(index))}><div className="daily-symbol accent">{text(item.symbol)}</div><div><strong>自由流通换手 {text(item.turnover_rate_f)}% · 当日 {pct(item.qfq_return_1d)}</strong><p>{text(item.narrative)}</p><small>相对 ST {pct(item.relative_st_1d)} · 相对中证2000 {pct(item.relative_csi_2000_1d)} · 3日 {pct(item.qfq_return_3d)} · 5日 {pct(item.qfq_return_5d)} · 历史 {text(item.history_count)} 日 · 分位 {text(item.turnover_percentile_120)} · z {text(item.turnover_robust_z_120)}</small></div></article>):<p className="daily-none">当日没有合格的 balanced 异常，或活动数据仍未达到发布门。</p>}</div></section>

    <section className="daily-section"><header><span>04</span><div><h2>联动研究队列</h2><p>排在前面表示先补证，不是收益排名。</p></div></header><div className="daily-queue">{payload.research_queue.length?payload.research_queue.map((item,index)=><article key={text(item.item_id,String(index))}><div className="daily-rank">{String(index+1).padStart(2,'0')}</div><div><span className={`priority ${text(item.priority)}`}>{text(item.priority)}</span><strong>{text(item.symbol)} · {text(item.relation)}</strong><p>{list(item.reasons).join('；')}</p><small><ScanSearch size={13}/>{text(item.first_check)} · P6 阶段 {nested(item.p6_context,'valuation_stage')}</small></div></article>):<p className="daily-none">当日没有联动研究任务。</p>}</div>{payload.overflow_count>0&&<p className="daily-overflow">另有 {payload.overflow_count} 条保存在完整账本中，页面只限制展示，不删历史真值。</p>}</section>

    <section className="daily-section"><header><span>05</span><div><h2>持续观察</h2><p>保留尚在合并观察窗内的历史异常线程，不因为今天没再次命中就消失。</p></div></header><div className="daily-stack">{payload.continuing_watch.length?payload.continuing_watch.map((item,index)=><article key={text(item.episode_id,String(index))}><div className="daily-symbol">{text(item.symbol)}</div><div><strong>上次命中 {text(item.last_hit_date)}</strong><p>{text(item.reason)}</p><small>{text(item.next_check)}</small></div></article>):<p className="daily-none">当前没有仍在观察窗内的历史异常线程。</p>}</div></section>

    <footer className="daily-foot"><CalendarDays size={15}/><span>checked-through：{Object.entries(payload.checked_through).map(([key,value])=>`${key} ${value||'—'}`).join(' · ')}</span><FileText size={15}/><span>{payload.contract_version}</span></footer>
  </div>
}
