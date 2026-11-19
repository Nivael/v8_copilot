import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-third-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('compares a common window and keeps the reversal visible',()=>{
 render(<STInitialFour data={data}/>);expect(screen.getByText(/50 → 54\/150/)).toBeVisible();expect(screen.getByText('-32.20%')).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}});expect(screen.getByText('+41.24%')).toBeVisible()
 expect(screen.getByText(/这不是上市公司自身重整失败/)).toBeVisible()
})
it('keeps old issue resolution distinct from new warning and exposes scanned source',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'000903'}})
 expect(screen.getByText(/不能把回顾旧立案状态/)).toBeVisible();fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'))
 expect(screen.getByText(/专项正文为扫描页，已逐页核对原图/)).toBeVisible()
 expect(screen.getByRole('link',{name:/2025年度财务报告非标准审计意见.*第4页/})).toHaveAttribute('href',expect.stringContaining('#page=4'))
})
it('updates Yigou shareholder approval without claiming payment or full recognition',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002024'}})
 expect(screen.getByText(/6月25日股东会已通过/)).toHaveTextContent('不应继续写成股东会待审')
 expect(screen.getByText(/豁免总额不等于当期利润或已到账现金/)).toBeVisible()
 fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/40%分期支付/)).toHaveTextContent('其他随支付确认')
})
it('retains all members and the 96 missing cases',()=>{
 render(<STInitialFour data={data}/>);fireEvent.click(screen.getByText('覆盖如何更新，哪些仍缺？'))
 const t=screen.getByRole('table',{name:'更新后的期初事实覆盖名单'});expect(within(t).getAllByRole('row')).toHaveLength(97)
 fireEvent.change(screen.getByRole('combobox',{name:'期初事实覆盖名单'}),{target:{value:'all'}});expect(within(t).getAllByRole('row')).toHaveLength(151)
})
