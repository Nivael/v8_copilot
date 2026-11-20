import {useState} from 'react'
import type {BreadthReading} from './readingTypes'
import {MarketBreadthContext} from './MarketBreadthContext'
import {MarketRecentBreadth} from './MarketRecentBreadth'
export function MarketBreadthReading({data,priceAsOf}:{data:BreadthReading;priceAsOf:string}){
 const [purpose,setPurpose]=useState<'today'|'recent'>('today')
 return <section id="market-participation" aria-label="市场参与面阅读"><div className="reading-purpose-switch" role="group" aria-label="广度阅读目的"><button type="button" aria-pressed={purpose==='today'} onClick={()=>setPurpose('today')}>当天跌得多广？</button><button type="button" aria-pressed={purpose==='recent'} onClick={()=>setPurpose('recent')}>这次怎样持续转弱？</button></div>{purpose==='today'?<MarketBreadthContext data={data} priceAsOf={priceAsOf}/>:<MarketRecentBreadth/>}</section>
}
