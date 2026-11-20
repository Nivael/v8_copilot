import {useEffect,useSyncExternalStore} from 'react'
import type {STRegimeData} from './stRegimeTypes'

export const caseQuestions = [
  {key:'marketstages',anchor:'st-market-stage-experience',title:'ST相对抗跌，为什么到10月就变了？',field:'market_stage_experience'},
  {key:'jihua',anchor:'st-jihua-bridge-followup',title:'际华：单季盈利与三项衔接差额怎样看？',field:'jihua_bridge_followup'},
  {key:'restatement',anchor:'st-restatement-comparison',title:'财报更正后，应该改哪一层判断？',field:'restatement_comparison'},
  {key:'yigou',anchor:'st-yigou-settlement',title:'易购：利润为正，和解与现金兑现了吗？',field:'yigou_settlement'},
  {key:'endpoints',anchor:'st-endpoint-reasons',title:'固定150只：缺价、停牌和退出怎样分别看？',field:'endpoint_reasons'},
  {key:'xilv',anchor:'st-xilv-timeline',title:'西旅：先跌后涨，公告和大盘分别说明了什么？',field:'xilv_timeline'},
  {key:'initialstatus',anchor:'st-initial-status-coverage',title:'期初样本：警示原因和后来走势怎样对应？',field:'initial_status_coverage'},
  {key:'dividends',anchor:'st-dividend-basis',title:'分红、重整与复权：同一天涨幅为何不同？',field:'dividend_basis'},
  {key:'quoteaudit',anchor:'st-fixed-quote-audit',title:'固定150只：行情核到哪一步，口径差异会改变结论吗？',field:'fixed_quote_audit'},
  {key:'prices',anchor:'st-stock-price-check',title:'沐邦、宝馨等五股：短线都涨，这几个月有什么不同？',field:'stock_price_crosscheck'},
  {key:'earnings',anchor:'st-earnings-warning',title:'天际等五家公司：盈利、现金和摘帽条件怎样分开看？',field:'earnings_warning'},
  {key:'cohort',anchor:'st-removal-cohort',title:'12只摘帽股：摘帽后是否普遍继续上涨？',field:'removal_cohort'},
  {key:'strong',anchor:'st-strong-removal-cases',title:'神雾、东晶：摘帽后涨得强，经营修复了吗？',field:'strong_removal_cases'},
  {key:'execution',anchor:'st-shenwu-execution',title:'神雾：过户、签约，距离现金到账还有多远？',field:'shenwu_execution'},
  {key:'followup',anchor:'st-removal-followup',title:'京蓝：摘帽、盈利之后，哪些风险仍需跟踪？',field:'removal_followup'},
  {key:'risk',anchor:'st-company-risk-cases',title:'高科、华鹏：相近跌幅背后，是同一种风险吗？',field:'company_risk_cases'},
  {key:'halts',anchor:'st-halt-stages',title:'岭南、龙元：同样停牌，后续程序一样吗？',field:'halt_stages'},
  {key:'issuer',anchor:'st-issuer-checks',title:'华鹏：后续财报与冻结，怎样更新7月判断？',field:'membership_audit'},
] as const
const mainAnchors:Record<string,string>={journey:'st-question-journey',market:'st-question-market',events:'st-question-events',lessons:'st-question-lessons'}
const subscribe=(notify:()=>void)=>{
  window.addEventListener('hashchange',notify)
  window.addEventListener('popstate',notify)
  return()=>{window.removeEventListener('hashchange',notify);window.removeEventListener('popstate',notify)}
}
const snapshot=()=>window.location.hash.slice(1)
export function availableQuestions(data:STRegimeData){
  return caseQuestions.filter(q=>q.key==='issuer'?Boolean(data.themes?.membership_audit?.issuer_checks?.length):Boolean(data.themes?.[q.field]))
}
export function useQuestionNavigation(data:STRegimeData){
  const hash=useSyncExternalStore(subscribe,snapshot,()=> '')
  const questions=availableQuestions(data)
  const baoxin=hash==='st-baoxin-auction-links'&&Boolean(data.themes?.baoxin_auction_links)
  const official=hash==='st-official-pdf-audit'&&Boolean(data.themes?.official_pdf_audit)
  const huke=hash==='st-huke-date-proof'&&Boolean(data.themes?.huke_date_proof)
  const selected=baoxin||official||huke?'events':questions.find(q=>q.anchor===hash)?.key??Object.keys(mainAnchors).find(k=>mainAnchors[k]===hash)??'journey'
  const known=baoxin||official||huke||questions.some(q=>q.anchor===hash)||Object.values(mainAnchors).includes(hash)
  useEffect(()=>{
    if(!known)return
    const frame=requestAnimationFrame(()=>document.getElementById(hash)?.scrollIntoView?.({block:'start'}))
    return()=>cancelAnimationFrame(frame)
  },[hash,known])
  function select(key:string){
    const anchor=key==='huke'&&data.themes?.huke_date_proof?'st-huke-date-proof':key==='baoxin'&&data.themes?.baoxin_auction_links?'st-baoxin-auction-links':questions.find(q=>q.key===key)?.anchor??mainAnchors[key]
    if(!anchor)return
    if(window.location.hash==='#'+anchor){document.getElementById(anchor)?.scrollIntoView?.({block:'start'});return}
    window.history.pushState(window.history.state,'','#'+anchor)
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }
  return {topic:selected,select,questions,companyOverride:baoxin?'002514':huke?'600608':null}
}
