import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STBreadthTiming} from './STBreadthTiming'
afterEach(cleanup)
it('separates already occurred moves, preceding anchor and incomplete following window',()=>{
 render(<STBreadthTiming/>);fireEvent.click(screen.getByText('等到三日条件成立，前面已经跌了多少？'))
 expect(screen.getByText(/不能当作下跌前预警/)).toBeVisible()
 const t=screen.getByRole('table');expect(t).toHaveTextContent('2026-11-11');expect(t).toHaveTextContent('-5.59%');expect(t).toHaveTextContent('-4.76%');expect(t).toHaveTextContent('未满5日')
 expect(screen.getByText(/前后复合，不能直接相加/)).toBeVisible()
})
