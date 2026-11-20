import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STExitObservation} from './STExitObservation'
afterEach(cleanup)
it('does not turn an absence of single-price candles into executable exit',()=>{
 render(<STExitObservation/>);fireEvent.click(screen.getByText('日线有成交，就能按复盘收盘价退出吗？'))
 expect(screen.getByText(/44个实际成交证券日/)).toBeVisible()
 expect(screen.getByText(/思科瑞停牌日也不计为成交/)).toBeVisible()
 expect(screen.getByRole('table',{name:'日线状态与实际可退出不同'})).toHaveTextContent('思科瑞6880538')
 expect(screen.getByText(/所选五家限价已补核/)).toBeVisible()
})

it('corrects a database-only gap without equating close-at-low with limit-down or executable exit',()=>{
 render(<STExitObservation/>);fireEvent.click(screen.getByText('日线有成交，就能按复盘收盘价退出吗？'))
 expect(screen.getByRole('region',{name:'限价留档恢复与更正'})).toHaveTextContent('45条证券日限价')
 expect(screen.getByText(/限价配对后/)).toHaveTextContent('2日收盘达到供应商下限价')
 fireEvent.click(screen.getByText('哪两日达到下限价，来源核到哪一步？'))
 const table=screen.getByRole('table',{name:'所选五家中，收盘达到已保存供应商下限价的证券日'})
 expect(table).toHaveTextContent('沐邦2026-11-19')
 expect(table).toHaveTextContent('威领2026-11-09')
 expect(screen.getByText(/主库缺近期数据不等于所有留档都缺/)).toBeVisible()
 expect(screen.getByText(/恢复原件不改变主库覆盖日期/)).toBeVisible()
})
