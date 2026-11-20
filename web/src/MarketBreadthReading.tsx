import {MarketRiskQuestions} from './MarketRiskQuestions'
import {STBreadthAlignment} from './STBreadthAlignment'
import {useState} from 'react'
import type {BreadthReading} from './readingTypes'
import {MarketBreadthContext} from './MarketBreadthContext'
import {MarketRecentBreadth} from './MarketRecentBreadth'
export function MarketBreadthReading({data,priceAsOf}:{data:BreadthReading;priceAsOf:string}){
 const [purpose,setPurpose]=useState<'overview'|'today'|'recent'|'st'>('overview')
 return <section id="market-participation" aria-label="市场参与面阅读"><div className="reading-purpose-switch" role="group" aria-label="广度阅读目的"><button type="button" aria-pressed={purpose==='overview'} onClick={()=>setPurpose('overview')}>先看风险线索</button><button type="button" aria-pressed={purpose==='today'} onClick={()=>setPurpose('today')}>当天跌得多广？</button><button type="button" aria-pressed={purpose==='recent'} onClick={()=>setPurpose('recent')}>这次怎样持续转弱？</button><button type="button" aria-pressed={purpose==='st'} onClick={()=>setPurpose('st')}>大盘转弱后，ST怎样？</button></div>{purpose==='overview'?<MarketRiskQuestions data={data} onRead={setPurpose}/>:purpose==='today'?<MarketBreadthContext data={data} priceAsOf={priceAsOf}/>:purpose==='recent'?<MarketRecentBreadth/>:<STBreadthAlignment/>}</section>
}
