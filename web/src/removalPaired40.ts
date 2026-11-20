import type {RegimeRemovalEraComparison,RemovalMatureWindows} from './stRegimeTypes'
const median=(values:number[])=>{const a=[...values].sort((x,y)=>x-y),m=Math.floor(a.length/2);return a.length%2?a[m]:(a[m-1]+a[m])/2}
export function removalPaired40(data:RemovalMatureWindows,prior:RegimeRemovalEraComparison){
 const rows=[];const waiting=[]
 for(const r of data.rows){
  const matches=prior.rows.filter(x=>x.era==='post'&&x.symbol===r.symbol)
  if(matches.length!==1||matches[0].resume_close_on!==r.anchor)return null
  const w=matches[0].windows['40']?.from_resume_close
  if(r.available_market_days<40){waiting.push({symbol:r.symbol,name:r.name,days:r.available_market_days,status:'insufficient_followup'});continue}
  if(!w||w.status!=='valid'||w.stock_pct===null||!w.through||w.anchor!==r.anchor){waiting.push({symbol:r.symbol,name:r.name,days:r.available_market_days,status:'needs_verification'});continue}
  if(r.certified_stock_pct===null||r.status!=='matched')continue
  const first=Number(r.certified_stock_pct),last=w.stock_pct
  if(!Number.isFinite(first)||!Number.isFinite(last)||first<=-100||last<=-100)return null
  rows.push({symbol:r.symbol,name:r.name,anchor:r.anchor,through20:r.through,through40:w.through,return20:first,return40:last,next20:((1+last/100)/(1+first/100)-1)*100})
 }
 if(!rows.length)return null
 return {rows,waiting,median20:median(rows.map(r=>r.return20)),median40:median(rows.map(r=>r.return40)),positive20:rows.filter(r=>r.return20>0).length,positive40:rows.filter(r=>r.return40>0).length,positive20StillPositive:rows.filter(r=>r.return20>0&&r.return40>0).length,gaveBack:rows.filter(r=>r.return20>0&&r.return40<r.return20-1e-9).length,extended:rows.filter(r=>r.return20>0&&r.return40>r.return20+1e-9).length}
}
