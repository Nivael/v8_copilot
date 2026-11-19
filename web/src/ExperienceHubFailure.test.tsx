import {cleanup,render,screen} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,expect,it,vi} from 'vitest'
import {ExperienceHub} from './ExperienceHub'
vi.mock('./useReadingView',()=>({useReadingView:()=>({packet:{availability:'warming',refresh:{in_progress:false,last_error:'ValueError'}},error:'本地数据核验未通过，暂时无法更新；已保存的研究仍保留',busy:false,reload:vi.fn()})}))
vi.mock('./STRegimeSection',()=>({STRegimeSection:()=>null}))
afterEach(cleanup)
it('shows a failed state and an enabled retry while preserving the research boundary',()=>{
 render(<MemoryRouter><ExperienceHub/></MemoryRouter>)
 expect(screen.getByRole('heading',{name:'跟踪记录暂时无法显示'})).toBeVisible()
 expect(screen.getByRole('alert')).toHaveTextContent('本地数据核验未通过')
 expect(screen.queryByText('正在读取跟踪记录')).not.toBeInTheDocument()
 expect(screen.getByRole('button',{name:'同步记录'})).toBeEnabled()
})
