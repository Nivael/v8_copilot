import type { Dossier, ResearchContext, StreamEvent } from './types'

export function parseNdjson(buffer:string, chunk:string){ const lines=`${buffer}${chunk}`.split('\n'); const remainder=lines.pop()??''; return {remainder,events:lines.map(x=>x.trim()).filter(Boolean).map(x=>JSON.parse(x) as StreamEvent)} }
export async function ask(question:string, context:ResearchContext, onEvent:(event:StreamEvent)=>void, signal?:AbortSignal){
  const response=await fetch('/api/v1/answers/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,object:context.symbol?{kind:'stock',ref:context.symbol}:null,context:Object.keys(context).length?context:null,llm_mode:'auto'}),signal})
  if(!response.ok||!response.body) throw new Error(`研究服务返回 ${response.status}`)
  const reader=response.body.getReader(); const decoder=new TextDecoder(); let buffer=''
  while(true){const {value,done}=await reader.read();if(done)break;const parsed=parseNdjson(buffer,decoder.decode(value,{stream:true}));buffer=parsed.remainder;parsed.events.forEach(onEvent)}
  if(buffer.trim())onEvent(JSON.parse(buffer) as StreamEvent)
}
export async function getDossier(symbol:string, signal?:AbortSignal):Promise<Dossier>{const response=await fetch(`/api/v1/stocks/${encodeURIComponent(symbol)}/dossier`,{signal});if(!response.ok)throw new Error(`个股证据服务返回 ${response.status}`);return response.json()}
