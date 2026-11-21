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
it('publishes completed dated scope while retaining the old partial stage',()=>{
 render(<DailySTExitPressure day="2026-11-20"/>);
 expect(screen.getByRole('table')).toHaveTextContent('146／150')
 expect(screen.getByRole('table')).toHaveTextContent('8只')
 expect(screen.getByRole('table')).toHaveTextContent('缺报价2只；无成交2只')
 expect(screen.getByRole('complementary')).toHaveTextContent('1只有成交但报价缺失')
 expect(screen.getByRole('complementary')).toHaveTextContent('72只有成交股票已全部核对')
 expect(screen.getByRole('complementary')).toHaveTextContent('*ST美丽')
 expect(screen.getByRole('complementary')).toHaveTextContent('补齐改变了覆盖完整性，未改变触限计数')
 expect(screen.getByRole('link',{name:'查看此前71只阶段与原缺口 →'})).toHaveTextContent('此前71只阶段')
})
