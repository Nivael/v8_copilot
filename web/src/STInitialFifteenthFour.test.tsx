import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-fifteenth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('explains correction without inventing risk removal',()=>{
 render(<STInitialFour data={data} readableAmounts/> )
 expect(screen.getByText(/98 → 102\/150家/)).toBeVisible()
 expect(screen.getByText(/万元改元已视觉核/)).toBeVisible()
})
it('leaves the suspended common endpoint empty and explains the reference price',()=>{
 render(<STInitialFour data={data}/> )
 fireEvent.change(screen.getByLabelText('期初四家比较窗口'),{target:{value:'early20'}})
 const row=within(screen.getByRole('table',{name:'期初四家风险与同窗表现'})).getByText('*ST椰岛').closest('tr')!
 expect(row.textContent).toMatch(/—|缺|停牌/)
 fireEvent.click(screen.getByText('共同价格端点，跨渠道核到哪一步？'))
 expect(screen.getByText(/4.14元仅是停牌参考值/)).toBeVisible()
 expect(screen.getByText('两渠道均无实际成交端点')).toBeVisible()
})
it('distinguishes expired obligations and accounting reclassification',()=>{
 render(<STInitialFour data={data} readableAmounts/> )
 fireEvent.change(screen.getByLabelText('选择公司核对期初原件'),{target:{value:'600239'}})
 expect(screen.getAllByText(/19.6亿元差额补足义务到期尚未履行/)[0]).toBeVisible()
 fireEvent.change(screen.getByLabelText('选择公司核对期初原件'),{target:{value:'600243'}})
 expect(screen.getAllByText(/权益内部重分类，不当新增利润或现金/)[0]).toBeVisible()
})
