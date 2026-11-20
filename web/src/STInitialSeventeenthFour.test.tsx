import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-seventeenth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value}})
it('shows initial risk rather than treating selected investors as a completed restructuring',()=>{
 render(<STInitialFour data={data} readableAmounts/> )
 expect(screen.getByText(/106 → 110\/150家/)).toBeVisible()
 expect(screen.getAllByText(/财报是保留意见，不是无法表示意见/)[0]).toBeVisible()
 expect(screen.getAllByText(/仍未签重整投资协议/)[0]).toBeVisible()
})
it('distinguishes old guarantees from the current individual obligations',()=>{
 render(<STInitialFour data={data}/>);company('600365')
 expect(screen.getAllByText(/20%范围内赔偿/)[0]).toBeVisible()
 company('600370');fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'))
 expect(screen.getAllByText(/旧2024年起始6亿元担保已履行完毕/)[0]).toBeVisible()
 expect(screen.getAllByRole('link',{name:/第120页/})[0]).toHaveAttribute('href',expect.stringContaining('#page=120'))
})
it('keeps applications pending and scanned original pages inspectable',()=>{
 render(<STInitialFour data={data}/>);company('600381')
 expect(screen.getAllByText(/申请结果仍以交易所审核为准/)[0]).toBeVisible()
 fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'))
 expect(screen.getAllByText(/文字提取为空不等于无内容/)[0]).toBeVisible()
 expect(screen.getAllByRole('link',{name:/第3页/})[0]).toHaveAttribute('href',expect.stringContaining('#page=3'))
})

it('uses readable units while keeping exact amounts behind the evidence disclosure',()=>{
 render(<STInitialFour data={data} readableAmounts/>);company('600381')
 expect(screen.getAllByText(/扣除后营收约3.33亿元/)[0]).toBeVisible()
 fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'))
 expect(screen.getByText(/披露2026-06-03，落款2026-06-02/)).toBeVisible()
})
