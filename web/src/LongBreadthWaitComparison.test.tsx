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
it('preserves one-day spells and shows the appended official endpoint control',()=>{
 render(<LongBreadthWaitComparison/>);fireEvent.change(screen.getByRole('combobox',{name:'选择偏弱片段'}),{target:{value:'2026-07-02'}})
 expect(screen.getByRole('table')).toHaveTextContent('片段不足2日')
 expect(screen.getByRole('table')).toHaveTextContent('片段不足3日')
 expect(screen.getByRole('complementary',{name:'七月二日指数补核'})).toHaveTextContent('7个收盘与主源按两位小数核同')
 expect(screen.getByRole('complementary',{name:'七月二日指数补核'})).toHaveTextContent('原显示收益仍沿用主源精度')
 expect(screen.getByRole('link',{name:'中证全指7月官方收盘来源 ↗'})).toHaveAttribute('href',expect.stringContaining('startDate=20260701'))
 expect(screen.getByText(/统一终点：2026-07-09/)).toBeVisible()
})
