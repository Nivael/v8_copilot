import {act,cleanup,renderHook,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {useReadingView} from './useReadingView'
afterEach(()=>{cleanup();vi.restoreAllMocks()})
const reply=(body:unknown)=>new Response(JSON.stringify(body),{status:200})
it('reports an idle verification failure rather than an endless successful warmup',async()=>{
 vi.spyOn(globalThis,'fetch').mockResolvedValue(reply({availability:'warming',refresh:{in_progress:false,last_error:'ValueError'}}))
 const {result}=renderHook(()=>useReadingView('history/failure'))
 await waitFor(()=>expect(result.current.error).toContain('本地数据核验未通过'))
 expect(result.current.busy).toBe(false)
})
it('does not label an active retry as a completed failure',async()=>{
 vi.spyOn(globalThis,'fetch').mockResolvedValue(reply({availability:'warming',refresh:{in_progress:true,last_error:'ValueError'}}))
 const {result}=renderHook(()=>useReadingView('history/retrying'))
 await waitFor(()=>expect(result.current.packet?.availability).toBe('warming'))
 expect(result.current.error).toBe('')
})
it('keeps verified cached records and warns when a subsequent update fails',async()=>{
 const data={questions:[{id:'saved'}]}
 const request=vi.spyOn(globalThis,'fetch').mockResolvedValueOnce(reply({availability:'available',data,refresh:{in_progress:false,last_error:null}})).mockResolvedValue(reply({availability:'warming',refresh:{in_progress:false,last_error:'ValueError'}}))
 const {result}=renderHook(()=>useReadingView<typeof data>('history/cached'))
 await waitFor(()=>expect(result.current.packet?.data).toEqual(data))
 act(()=>result.current.reload())
 await waitFor(()=>expect(result.current.error).toContain('已保存的研究仍保留'))
 expect(result.current.packet?.data).toEqual(data)
 expect(request).toHaveBeenCalledTimes(2)
})
it('manual learning refresh requests a server retry without changing automatic reads',async()=>{
 const request=vi.spyOn(globalThis,'fetch').mockImplementation(async()=>reply({availability:'available',data:{methods:[]},refresh:{in_progress:false,last_error:null}}))
 const {result}=renderHook(()=>useReadingView('learning'))
 await waitFor(()=>expect(result.current.packet?.availability).toBe('available'))
 act(()=>result.current.reload())
 await waitFor(()=>expect(request).toHaveBeenCalledTimes(2))
 expect(String(request.mock.calls[0][0])).toBe('/api/v1/workbench/learning')
 expect(String(request.mock.calls[1][0])).toBe('/api/v1/workbench/learning?refresh=true')
})
