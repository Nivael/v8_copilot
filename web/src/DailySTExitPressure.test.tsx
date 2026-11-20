import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {DailySTExitPressure} from './DailySTExitPressure'
afterEach(cleanup)
it('keeps two overlapping cohorts and missing quotes visible',()=>{
 render(<DailySTExitPressure day="2026-11-17"/>);
 const table=screen.getByRole('table')
 expect(table).toHaveTextContent('141／142')
 expect(table).toHaveTextContent('10只')
 expect(table).toHaveTextContent('固定历史150只')
 expect(screen.getByRole('complementary')).toHaveTextContent('各列不能相加')
})
it('does not fill an uncovered historical date with zero',()=>{
 render(<DailySTExitPressure day="2026-07-01"/>);
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
 expect(screen.getByRole('complementary')).toHaveTextContent('状态未知，不等于没有跌停')
})
it('keeps Nov20 partial scope apart from the prior nine-day groups',()=>{
 render(<DailySTExitPressure day="2026-11-20"/>);
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
 expect(screen.getByRole('complementary')).toHaveTextContent('1只有成交但报价缺失')
 expect(screen.getByRole('complementary')).toHaveTextContent('不代表全部72只有成交样本')
})
