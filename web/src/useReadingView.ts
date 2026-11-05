import {useCallback,useEffect,useState} from 'react'
import type {ReadingPacket} from './readingTypes'

const cache=new Map<string,ReadingPacket<unknown>>()

export function useReadingView<T>(kind:'market'|'learning'){
  const [packet,setPacket]=useState<ReadingPacket<T>|undefined>(()=>cache.get(kind) as ReadingPacket<T>|undefined)
  const [error,setError]=useState('')
  const [request,setRequest]=useState(0)
  const [busy,setBusy]=useState(false)
  const reload=useCallback(()=>setRequest(value=>value+1),[])
  useEffect(()=>{
    const controller=new AbortController()
    let timer:ReturnType<typeof setTimeout>|undefined
    let active=true
    let inFlight=false
    async function read(force=false){
      if(inFlight||!active)return
      inFlight=true
      setBusy(true)
      try{
        const response=await fetch(`/api/v1/workbench/${kind}${force?'?refresh=true':''}`,{signal:controller.signal,cache:'no-store'})
        if(!response.ok)throw new Error('暂时无法连接本地面板服务')
        const value=await response.json() as ReadingPacket<T>
        if(!active)return
        if(value.availability==='available'&&value.data){cache.set(kind,value);setPacket(value)}
        else setPacket(previous=>previous?.data?previous:value)
        setError('')
        timer=setTimeout(()=>{if(document.visibilityState!=='hidden')void read()},value.refresh.in_progress||value.availability==='warming'?2000:30000)
      }catch(reason){if(active&&!controller.signal.aborted)setError(reason instanceof Error?reason.message:'读取失败')}
      finally{inFlight=false;if(active)setBusy(false)}
    }
    const focus=()=>{if(document.visibilityState!=='hidden'){clearTimeout(timer);void read()}}
    void read(request>0&&kind==='market')
    window.addEventListener('focus',focus)
    document.addEventListener('visibilitychange',focus)
    return()=>{active=false;controller.abort();clearTimeout(timer);window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',focus)}
  },[kind,request])
  return{packet,error,busy,reload}
}
