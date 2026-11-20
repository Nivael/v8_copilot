import type {RegimeThemes,RemovalMatureWindows} from './stRegimeTypes'
type Point={date:string;status:string;primary_close:string|null;cross_close:string|null}
type EventWindow={requested_days:number;observed_days:number;anchor:string|null;through:string|null;stock_pct:string|null;market_pct:string|null;stock_quote_check?:string}
export type RemovalClocksInput={mature:RemovalMatureWindows;latest_rows:{symbol:string;endpoints:Point[]}[];market_path:{date:string;market:number}[];events:{aid?:string;symbol:string;published_on?:string;windows:EventWindow[]}[];event_reviews:{aid:string;symbol:string;requested_days:number;status:string}[];sources:{announcement_id:string;title:string;url:string;sha256?:string;published_on?:string}[]}
export function removalClocksInput(themes?:RegimeThemes|null):RemovalClocksInput|null{
 const m=themes?.removal_mature_windows,latest=themes?.market_stage_experience,ext=themes?.current_extension,rest=themes?.restatement_comparison,period=themes?.twentyfourth_period_followup
 if(!m||!latest||!ext?.path||!rest||!period)return null
 const stage=latest.stages.find(s=>s.through===m.through)
 if(!stage)return null
 return {mature:m,latest_rows:stage.rows,market_path:ext.path,events:[...rest.event_windows,...period.event_windows],event_reviews:rest.window_reviews??[],sources:[...rest.source_refs,...period.sources]}
}
export function removalAnnouncementClocks(input:RemovalClocksInput){
 const market=new Map(input.market_path.map(r=>[r.date,r.market]));const result=[]
 for(const symbol of ['603838','603517']){
  const row=input.mature.rows.find(r=>r.symbol===symbol),latest=input.latest_rows.find(r=>r.symbol===symbol)?.endpoints.find(e=>e.date===input.mature.through)
  if(!row||row.anchor!=='2026-10-20'||!row.through||!latest)return null
  const start=row.endpoints.find(e=>e.date===row.anchor),end20=row.endpoints.find(e=>e.date===row.through)
  if(!start||!end20)return null
  const windows=[]
  for(const [label,end]of [['首日收盘后20日',end20],['首日收盘至最新',latest]] as const){
   const a=market.get(start.date),z=market.get(end.date)
   if(a===undefined||z===undefined||a<=0||!Number.isFinite(a)||!Number.isFinite(z))return null
   const good=start.status==='matched'&&end.status==='matched'
   const prices=[start.primary_close,end.primary_close,start.cross_close,end.cross_close].map(x=>x===null?NaN:Number(x))
   if(prices.some(x=>!Number.isFinite(x)||x<=0))return null
   windows.push({label,anchor:start.date,through:end.date,certified:good?(prices[1]/prices[0]-1)*100:null,primary:(prices[1]/prices[0]-1)*100,cross:(prices[3]/prices[2]-1)*100,market:(z/a-1)*100,observed:null as number|null})
  }
  const aid=symbol==='603838'?'1225629182':'1225630481';const event=input.events.find(e=>e.aid===aid&&e.symbol===symbol);const w=event?.windows.find(w=>w.requested_days===20&&w.through===input.mature.through)
  const matched=w?.stock_quote_check==='matched'||input.event_reviews.some(r=>r.aid===aid&&r.symbol===symbol&&r.requested_days===20&&r.status==='matched')
  if(!w||!w.anchor||!w.through||w.stock_pct===null||w.market_pct===null||!matched||![Number(w.stock_pct),Number(w.market_pct)].every(Number.isFinite))return null
  windows.push({label:'更正或季报前收盘至最新',anchor:w.anchor,through:w.through,certified:Number(w.stock_pct),primary:Number(w.stock_pct),cross:Number(w.stock_pct),market:Number(w.market_pct),observed:w.observed_days})
  result.push({symbol,name:row.name,windows})
 }
 const ids=['1225608268','1225629182','1225629255','1225609996','1225610029','1225630481','1225676244']
 const sources=ids.map(id=>input.sources.find(s=>s.announcement_id===id))
 if(sources.some(s=>!s)||sources[6]?.published_on!=='2026-11-18')return null
 return {through:input.mature.through,cases:result,sources:sources.filter((s):s is NonNullable<typeof s>=>Boolean(s))}
}
