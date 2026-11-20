import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {LongBreadthSTComparison} from './LongBreadthSTComparison'
afterEach(cleanup)
it('shows all six first hits and separates partial outcome and historical boundary',()=>{
 render(<LongBreadthSTComparison priceAsOf="2026-11-20"/>);fireEvent.click(screen.getByText('连续转弱后一定继续跌吗？把7—11月一起看'))
 const t=screen.getByRole('table');expect(t.querySelectorAll('tbody tr')).toHaveLength(6)
 expect(t).toHaveTextContent('2026-07-20完整5日截至2026-07-27+2.09%+3.00%')
 expect(t).toHaveTextContent('2026-09-04完整5日截至2026-09-11+0.17%-1.05%')
 expect(t).toHaveTextContent('仅3日，未满5日')
 fireEvent.click(screen.getByText('新增历史怎样改变了观察，哪些仍不能推出？'))
 expect(screen.getByText(/缺少9月2、3日前序/)).toBeVisible()
})
it('does not redate the frozen comparison',()=>{render(<LongBreadthSTComparison priceAsOf="2026-11-23"/>);expect(screen.queryByRole('table')).not.toBeInTheDocument()})
