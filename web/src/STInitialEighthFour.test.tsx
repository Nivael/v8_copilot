import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-eighth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('shows opposing paths and keeps the early window selectable',()=>{
 render(<STInitialFour data={data} readableAmounts/>);expect(screen.getByText(/70 → 74\/150/)).toBeVisible();const t=screen.getByRole('table',{name:'期初四家风险与同窗表现'});expect(within(t).getByText('+18.08%')).toBeVisible();expect(within(t).getByText('-27.10%')).toBeVisible();fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}});expect(within(t).getByText('+4.02%')).toBeVisible()
})
it('updates the shareholder meeting without claiming court acceptance',()=>{
 render(<STInitialFour data={data}/>);expect(screen.getByText(/6月18日股东会已通过/)).toBeVisible();expect(screen.getByText(/股东会通过不当法院已受理/)).toBeVisible()
})
it('keeps the conflicting issuer text alongside direct audit evidence',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002634'}});fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/直接会计师专项明确无保留意见/)).toBeVisible();expect(screen.getByText(/与直接会计师意见冲突/)).toBeVisible();expect(screen.getByText(/约定不证明已付款/)).toBeVisible()
})
it('keeps visual signature proof distinct from extracted source text',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002581'}});fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/签章页提取为空/)).toHaveTextContent('未修改原提取正文')
})
it('preserves all 150 rows and 76 uncovered companies',()=>{
 render(<STInitialFour data={data}/>);fireEvent.click(screen.getByText('覆盖如何更新，哪些仍缺？'));const t=screen.getByRole('table',{name:'更新后的期初事实覆盖名单'});expect(within(t).getAllByRole('row')).toHaveLength(77);fireEvent.change(screen.getByRole('combobox',{name:'期初事实覆盖名单'}),{target:{value:'all'}});expect(within(t).getAllByRole('row')).toHaveLength(151)
})
