import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {RunAudit} from './RunAudit'
import source from './fixtures/longStudyLabelRuns.json'
afterEach(()=>{cleanup();vi.restoreAllMocks()})
it('shows corrected headings while keeping raw text accessible',async()=>{
 vi.spyOn(globalThis,'fetch').mockImplementation(async input=>new Response(JSON.stringify(String(input).includes('corrections')?{availability:'available',corrections:[]}:[source[2]])))
 render(<MemoryRouter><RunAudit/></MemoryRouter>)
 const note=await screen.findByRole('complementary',{name:'研究说明标题更正'})
 expect(note).toHaveTextContent('原始登记与校验记录未改写')
 expect(screen.getByText('短片段覆盖与同终点比较')).toBeVisible()
 fireEvent.click(within(note).getByText('查看标题更正及原始说明'))
 expect(note.querySelector('pre')?.textContent).toBe(source[2].final_answer)
 expect(note.querySelector('pre')).toBeVisible()
 expect(screen.getByRole('region',{name:'本次研究反馈'})).toBeVisible()
})
