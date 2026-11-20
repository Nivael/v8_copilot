import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STExitObservation} from './STExitObservation'
afterEach(cleanup)
it('does not turn an absence of single-price candles into executable exit',()=>{
 render(<STExitObservation/>);fireEvent.click(screen.getByText('日线有成交，就能按复盘收盘价退出吗？'))
 expect(screen.getByText(/44个实际成交证券日/)).toBeVisible()
 expect(screen.getByText(/思科瑞停牌日也不计为成交/)).toBeVisible()
 expect(screen.getByRole('table')).toHaveTextContent('思科瑞6880538')
 expect(screen.getByText(/目前缺实际限价和盘口队列/)).toBeVisible()
})
