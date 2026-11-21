import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {FixedLimitTransition} from './FixedLimitTransition'
afterEach(cleanup)
it('keeps lower-bound departures separate from daily price recovery and includes all departures',()=>{
 render(<FixedLimitTransition/>);
 expect(screen.getByRole('region',{name:'同成员封限与价格变化'})).toHaveTextContent('6只离开收盘下限者中，5只当天仍跌、1只上涨')
 expect(screen.getByRole('table',{name:'同一批股票的完整收盘状态转移，不挑选修复案例'})).toHaveTextContent('138')
 const rows=screen.getByRole('table',{name:'全部六只，包含继续下跌者'}).querySelectorAll('tbody tr')
 expect(rows).toHaveLength(6)
 expect(screen.getByRole('link')).toHaveAttribute('href','/runs#research-RUN-B3049BEEE3C6406994404510')
})
