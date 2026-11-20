import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {STCashPlanFollowup} from './STCashPlanFollowup'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
const data={content_digest:'e0ed59aa8cc346fc45349f5daac23d091211c82c145b91c38d031e47579e612f'} as STRegimeData
it('separates receipt, another gift, approval and execution while preserving dates',()=>{
 render(<STCashPlanFollowup data={data}/>);
 expect(screen.getByText(/截至11月18日，12000万元已划转/)).toBeVisible()
 expect(screen.getByText(/不能从这份文件认证合计1.4亿元全部到账/)).toBeInTheDocument()
 expect(screen.getByText(/并终止重整程序，随后进入计划执行阶段/)).toBeVisible()
 expect(screen.getByText(/不等于计划执行完毕/)).toBeInTheDocument()
})
it('shows only the selected company on the older timeline without mutating it',()=>{
 const before=JSON.stringify(data);render(<STCashPlanFollowup data={data} symbol="000609"/>);
 expect(screen.getByText(/中迪：第一笔1.2亿元/)).toBeVisible()
 expect(screen.queryByText(/西发：计划获批/)).not.toBeInTheDocument()
 expect(JSON.stringify(data)).toBe(before)
})
it('withholds source-bound updates when the original snapshot changes',()=>{
 render(<STCashPlanFollowup data={{...data,content_digest:'changed'}}/>);
 expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
})
