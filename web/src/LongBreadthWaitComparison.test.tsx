import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {LongBreadthWaitComparison} from './LongBreadthWaitComparison'
afterEach(cleanup)
it('uses one endpoint and keeps different remaining durations visible',()=>{
 render(<LongBreadthWaitComparison/>);
 expect(screen.getByRole('combobox',{name:'选择偏弱片段'}).querySelectorAll('option')).toHaveLength(27)
 expect(screen.getByText(/统一终点：2026-11-19/)).toBeVisible()
 const t=screen.getByRole('table');expect(t).toHaveTextContent('5个交易日');expect(t).toHaveTextContent('4个交易日');expect(t).toHaveTextContent('3个交易日')
 expect(screen.getByText(/不是这段已经结束的证明/)).toBeVisible()
})
it('preserves one-day spells and their primary-only index boundary',()=>{
 render(<LongBreadthWaitComparison/>);fireEvent.change(screen.getByRole('combobox',{name:'选择偏弱片段'}),{target:{value:'2026-07-02'}})
 expect(screen.getByRole('table')).toHaveTextContent('片段不足2日')
 expect(screen.getByRole('table')).toHaveTextContent('片段不足3日')
 expect(screen.getByText(/7月2日收益尚不在该交叉核对范围/)).toBeVisible()
 expect(screen.getByText(/统一终点：2026-07-09/)).toBeVisible()
})
