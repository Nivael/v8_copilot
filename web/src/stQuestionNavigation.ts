import {useEffect,useSyncExternalStore} from 'react'
import type {STRegimeData} from './stRegimeTypes'

export const caseQuestions = [
  {key:'dividends',anchor:'st-dividend-basis',title:'章鼓、八菱：同一天的涨幅，为什么有三种读数？',field:'dividend_basis'},
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
  const selected=questions.find(q=>q.anchor===hash)?.key??Object.keys(mainAnchors).find(k=>mainAnchors[k]===hash)??'journey'
  const known=questions.some(q=>q.anchor===hash)||Object.values(mainAnchors).includes(hash)
  useEffect(()=>{
    if(!known)return
    const frame=requestAnimationFrame(()=>document.getElementById(hash)?.scrollIntoView?.({block:'start'}))
    return()=>cancelAnimationFrame(frame)
  },[hash,known])
  function select(key:string){
    const anchor=questions.find(q=>q.key===key)?.anchor??mainAnchors[key]
    if(!anchor)return
    if(window.location.hash==='#'+anchor){document.getElementById(anchor)?.scrollIntoView?.({block:'start'});return}
    window.history.pushState(window.history.state,'','#'+anchor)
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }
  return {topic:selected,select,questions}
}
