import {cleanup,render,screen,waitFor} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,it,expect,vi} from 'vitest'
import {ExperienceHub} from './ExperienceHub'
import {learningReading} from './test/readingFixtures'
import type {CurrentExtension} from './STCurrentExtension'
vi.mock('./STRegimeSection',async()=>{
 const {useEffect}=await import('react');const data=(await import('./__fixtures__/current-extension.json')).default as CurrentExtension
 return {STRegimeSection:({onCurrentUpdate}:{onCurrentUpdate?:(d:CurrentExtension|null)=>void})=>{useEffect(()=>{onCurrentUpdate?.(data)},[onCurrentUpdate]);return null}}
})
vi.mock('./SwingWatchSection',()=>({SwingWatchSection:()=>null}))
afterEach(()=>{cleanup();vi.restoreAllMocks()})
it('connects the published update to the selected historical case without relabeling its old price or adding a fetch',async()=>{
 const request=vi.spyOn(globalThis,'fetch').mockImplementation(async()=>new Response(JSON.stringify({availability:'available',as_of:'2026-11-04',data:learningReading,refresh:{in_progress:false,last_error:null}})))
 render(<MemoryRouter><ExperienceHub/></MemoryRouter>)
 await screen.findByRole('heading',{name:'*ST沐邦：新进展推进到哪一步？'})
 expect(screen.getByText(/历史收盘 · 当日/)).toHaveTextContent('2026-11-04')
 expect(screen.getByText(new Date(learningReading.cases[0].history[0].completed_at).toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'})+' 的研究结论')).toBeVisible()
 await waitFor(()=>expect(request).toHaveBeenCalledTimes(1))
 expect(String(request.mock.calls[0][0])).toBe('/api/v1/workbench/learning')
})
