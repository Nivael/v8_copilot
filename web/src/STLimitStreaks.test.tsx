import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STLimitCohorts} from './STLimitCohorts'
afterEach(cleanup)
it('distinguishes four closing limits from two single-price days and keeps unfinished right boundary',()=>{
 render(<STLimitCohorts/>);fireEvent.click(screen.getByText('把限价核到整个样本后，压力怎样变化？'));fireEvent.click(screen.getByText('连续出现时，窗口里能确认几天？'))
 const t=screen.getByRole('table',{name:'连续收盘达到下限：已观察长度与未核边界'})
 expect(t).toHaveTextContent('*ST瑞茂');expect(t).toHaveTextContent('4个交易日');expect(t).toHaveTextContent('20日状态未核')
 expect(screen.getByText(/截至2026-11-19的九日窗口内/)).toHaveTextContent('5家公司')
 fireEvent.click(screen.getByRole('button',{name:'连续全天同价跌停'}))
 const single=screen.getByRole('table',{name:'连续全天同价跌停：已观察长度与未核边界'})
 expect(single).toHaveTextContent('*ST启环');expect(single).toHaveTextContent('2个交易日')
 expect(single).not.toHaveTextContent('*ST瑞茂')
})
it('follows parent cohort selection without counting overlapping cases twice',()=>{
 render(<STLimitCohorts/>);fireEvent.click(screen.getByText('把限价核到整个样本后，压力怎样变化？'));fireEvent.click(screen.getByText('连续出现时，窗口里能确认几天？'))
 fireEvent.click(screen.getByRole('button',{name:'固定150只原始样本'}))
 expect(screen.getByText(/固定150只原始样本 · 连续收盘/)).toBeVisible()
 fireEvent.click(screen.getByText('连续段怎样计数，哪些仍未知？'))
 expect(screen.getByText(/本组23个成员证券日未配对/)).toBeVisible()
 expect(screen.getByText(/两组重叠股票和两种状态不增加独立案例/)).toBeVisible()
})
