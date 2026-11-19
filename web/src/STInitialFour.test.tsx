import {cleanup,render,screen,fireEvent,within} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('leads with shared dates and four risk contexts without a return-based ranking',()=>{
 render(<STInitialFour data={data}/>)
 expect(screen.getByText(/42 → 46\/150家/)).toHaveTextContent('仍缺104家')
 const table=screen.getByRole('table',{name:'期初四家风险与同窗表现'})
 expect(table).toHaveTextContent('-31.25%');expect(table).toHaveTextContent('+20.96%')
 expect(screen.getByText(/西旅最初20日为/)).toHaveTextContent('-6.93%')
 expect(screen.getByText(/12个前复权共同端点/)).toHaveTextContent('6个端点')
 expect(screen.getByText(/93个交易日/)).toHaveTextContent('2026-07-03收盘 → 2026-11-19')
 fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}})
 expect(screen.getByText(/2026-07-03收盘 → 2026-07-31/)).toHaveTextContent('2026-07-31')
})
it('keeps Chenming remediation and B-only abnormal trading apart from A-share risk removal',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'000488'}})
 expect(screen.getByText(/2026年3月已有整改/)).toBeVisible()
 fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'))
 expect(screen.getByText(/异动对象是B股200488/)).toHaveTextContent('不作为A股异动')
 expect(screen.getByText(/内控专项明确/)).toHaveTextContent('不是正式摘帽决定')
 expect(screen.getByText(/报表列示段落含2024年度/)).toBeVisible()
})
it('uses Xilv body implementation date without treating a proposed financing as paid',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'000610'}})
 expect(screen.getByText(/标题含“可能”/)).toHaveTextContent('正文已列4月27日实施')
 expect(screen.getByText(/标题含“可能”/)).toHaveTextContent('不等于已经募集或到账')
})
it('retains all 150 members and exposes the 104 remaining gaps',()=>{
 render(<STInitialFour data={data}/>);fireEvent.click(screen.getByText('覆盖如何更新，哪些仍缺？'))
 const table=screen.getByRole('table',{name:'更新后的期初事实覆盖名单'})
 expect(within(table).getAllByRole('row')).toHaveLength(105)
 fireEvent.change(screen.getByRole('combobox',{name:'期初事实覆盖名单'}),{target:{value:'all'}})
 expect(within(table).getAllByRole('row')).toHaveLength(151)
 expect(screen.getByText(/按旧150只缺口名单的代码顺序/)).toBeVisible()
})
