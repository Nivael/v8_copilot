import type {MarketStageExperience} from './stRegimeTypes'
const epsilon=1e-9
const sign=(n:number)=>Math.abs(n)<epsilon?0:n>0?1:-1
const median=(values:number[])=>{const a=[...values].sort((x,y)=>x-y);const m=Math.floor(a.length/2);return a.length%2?a[m]:(a[m-1]+a[m])/2}
export function recoveryPath(data:MarketStageExperience){
 const stages=data.stages
 if(stages.length!==5)return null
 const members=stages[0].common_sample.symbols
 if(!members.length||new Set(members).size!==members.length)return null
 const rows:{symbol:string;cumulative:number[];augustRose:boolean}[]=[]
 for(const symbol of members){
  const prices:number[]=[]
  for(let j=0;j<stages.length;j++){
   const stage=stages[j];const matches=stage.rows.filter(r=>r.symbol===symbol)
   if(matches.length!==1||!stage.common_sample.symbols.includes(symbol))return null
   const r=matches[0]
   if(r.status!=='matched'||r.endpoints.length!==2||r.endpoints.some(e=>e.status!=='matched'||e.primary_close===null))return null
   if(r.endpoints[0].date!==stage.anchor||r.endpoints[1].date!==stage.through)return null
   const [a,z]=r.endpoints.map(e=>Number(e.primary_close))
   if(!Number.isFinite(a)||!Number.isFinite(z)||a<=0||z<=0)return null
   if(j===0)prices.push(a)
   else if(stages[j-1].through!==stage.anchor||Math.abs(prices[j]-a)>epsilon)return null
   prices.push(z)
  }
  const cumulative=prices.slice(1).map(p=>(p/prices[0]-1)*100)
  rows.push({symbol,cumulative,augustRose:prices[2]>prices[1]+epsilon})
 }
 const summaries=stages.map((s,j)=>{const values=rows.map(r=>r.cumulative[j]);return {through:s.through,positive:values.filter(v=>sign(v)>0).length,zero:values.filter(v=>sign(v)===0).length,negative:values.filter(v=>sign(v)<0).length,median:median(values)}})
 const julyLosers=rows.filter(r=>sign(r.cumulative[0])<0)
 const augustPositive=rows.filter(r=>sign(r.cumulative[1])>0)
 return {rows,summaries,members:members.length,anchor:stages[0].anchor,julyLosers:julyLosers.length,augustRose:julyLosers.filter(r=>r.augustRose).length,recovered:julyLosers.filter(r=>sign(r.cumulative[1])>=0).length,augustPositive:augustPositive.length,stillPositive:augustPositive.filter(r=>sign(r.cumulative[4])>0).length}
}
