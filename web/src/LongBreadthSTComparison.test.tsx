import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {LongBreadthSTComparison} from './LongBreadthSTComparison'
afterEach(cleanup)
it('shows all six first hits and separates partial outcome and historical boundary',()=>{
 render(<LongBreadthSTComparison priceAsOf="2026-11-20"/>);fireEvent.click(screen.getByText('连续转弱后一定继续跌吗？把7—11月一起看'))
 const t=screen.getByRole('table',{name:'全部六次提示：同一提示后的ST与大盘，未满窗口单列'});expect(t.querySelectorAll('tbody tr')).toHaveLength(6)
 expect(t).toHaveTextContent('2026-07-20完整5日截至2026-07-27+2.09%+3.00%')
 expect(t).toHaveTextContent('2026-09-04完整5日截至2026-09-11+0.17%-1.05%')
 expect(t).toHaveTextContent('仅3日，未满5日')
 fireEvent.click(screen.getByText('新增历史怎样改变了观察，哪些仍不能推出？'))
 expect(screen.getByText(/缺少9月2、3日前序/)).toBeVisible()
})
it('does not redate the frozen comparison',()=>{render(<LongBreadthSTComparison priceAsOf="2026-11-23"/>);expect(screen.queryByRole('table')).not.toBeInTheDocument()})
it('switches between confirmation-window changes and following outcomes without mixing them',()=>{
 render(<LongBreadthSTComparison priceAsOf="2026-11-20"/>);fireEvent.click(screen.getByText('连续转弱后一定继续跌吗？把7—11月一起看'))
 fireEvent.click(screen.getByRole('button',{name:'确认时已发生什么？'}))
 expect(screen.getByRole('button',{name:'确认时已发生什么？'})).toHaveAttribute('aria-pressed','true')
 expect(screen.getByRole('table')).toHaveTextContent('2026-07-202026-07-15收盘-8.39%-7.19%')
 expect(screen.getByRole('table')).toHaveTextContent('2026-09-042026-09-01收盘+0.25%-1.84%')
 expect(screen.getByText(/不是提前预警或你的账户损失/)).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:'提示后怎样？'}))
 expect(screen.getByRole('table',{name:'全部六次提示：同一提示后的ST与大盘，未满窗口单列'})).toHaveTextContent('仅3日，未满5日')
})
