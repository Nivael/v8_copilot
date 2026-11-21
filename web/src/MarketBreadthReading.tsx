import {FixedLimitTransition} from './FixedLimitTransition'
import {DailyMarketLimitPressure} from './DailyMarketLimitPressure'
import {DailySTExitPressure} from './DailySTExitPressure'
import {BreadthSeverityTiming} from './BreadthSeverityTiming'
import {MarketRiskQuestions} from './MarketRiskQuestions'
import {STBreadthAlignment} from './STBreadthAlignment'
import {useEffect,useRef,useState} from 'react'
import type {BreadthReading} from './readingTypes'
import {MarketBreadthContext} from './MarketBreadthContext'
import {MarketRecentBreadth} from './MarketRecentBreadth'
export function MarketBreadthReading({data,priceAsOf}:{data:BreadthReading;priceAsOf:string}){
 const reader=useRef<HTMLElement>(null)
 const [purpose,setPurpose]=useState<'overview'|'today'|'recent'|'st'|'severity'|'limits'>('overview')
 useEffect(()=>{if((purpose==='severity'||purpose==='limits'))reader.current?.scrollIntoView?.({block:'start'})},[purpose])
 return <section ref={reader} style={{scrollMarginTop:80}} id="market-participation" aria-label="市场参与面阅读"><div className="reading-purpose-switch" role="group" aria-label="广度阅读目的"><button type="button" aria-pressed={purpose==='overview'} onClick={()=>setPurpose('overview')}>先看风险线索</button><button type="button" aria-pressed={purpose==='today'} onClick={()=>setPurpose('today')}>当天跌得多广？</button><button type="button" aria-pressed={purpose==='recent'} onClick={()=>setPurpose('recent')}>这次怎样持续转弱？</button><button type="button" aria-pressed={purpose==='st'} onClick={()=>setPurpose('st')}>大盘转弱后，ST怎样？</button><button type="button" aria-pressed={purpose==='severity'} onClick={()=>setPurpose('severity')}>冲击与持续性怎样分开看？</button><button type="button" aria-pressed={purpose==='limits'} onClick={()=>setPurpose('limits')}>封限减少，风险缓和了吗？</button></div>{purpose==='limits'?<section aria-label="限价与退出阅读"><h2>先分清封限减少、价格回升与能否退出</h2>{data.as_of==='2026-11-20'?<FixedLimitTransition expanded/>:<p role="status">同成员状态对照截至11月20日，不套用到所选的新日期。</p>}<DailyMarketLimitPressure day={data.as_of} trading={data.groups[0]?.observed_trading_stocks??0}/><DailySTExitPressure day={data.as_of} showTransition={false}/></section>:purpose==='severity'?<section aria-label="冲击与持续性阅读"><h2>没连续弱三日，也可能已经大跌</h2><BreadthSeverityTiming expanded asOf={data.as_of}/></section>:purpose==='overview'?<MarketRiskQuestions data={data} onRead={setPurpose}/>:purpose==='today'?<MarketBreadthContext data={data} priceAsOf={priceAsOf}/>:purpose==='recent'?<MarketRecentBreadth/>:<STBreadthAlignment/>}</section>
}
