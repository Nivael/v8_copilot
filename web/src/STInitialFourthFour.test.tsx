import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-fourth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('compares repairs with actual later outcomes and retains the counterexample',()=>{
 render(<STInitialFour data={data}/>);expect(screen.getByText(/54 → 58\/150/)).toBeVisible();const t=screen.getByRole('table',{name:'期初四家风险与同窗表现'});expect(within(t).getByText('+5.49%')).toBeVisible();expect(within(t).getByText('-26.70%')).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}});expect(within(t).getByText('-7.06%')).toBeVisible()
})
it('keeps a scanned internal-control repair separate from court-specific asset restraints',()=>{
 render(<STInitialFour data={data}/>);expect(screen.getByText(/不是全部资金均以现金收回/)).toBeVisible();fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/专项第3页为扫描页/)).toBeVisible();expect(screen.getByText(/璧山法院解除得润大厦查封/)).toHaveTextContent('同一资产不同案件不能净成全面解封')
})
it('updates Huicheng from application to approved partial removal',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002168'}});expect(screen.getByText(/5月11日起已正式撤销/)).toHaveTextContent('不再只写申请待审');expect(screen.getByText(/5月11日起已正式撤销/)).toHaveTextContent('继续ST')
})
it('preserves Ruyi clock conflict and unquantified audit effect',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002193'}});expect(screen.getByText(/审计师无法合理估计影响金额/)).toBeVisible();fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/第5页引述规则从决定作出日起算/)).toHaveTextContent('保留原文差异');expect(screen.getByText(/财报保留基础为佛山莱卡/)).toHaveTextContent('不能把账面额直接当损失')
})
it('retains all 150 and exposes the remaining 92 gaps',()=>{
 render(<STInitialFour data={data}/>);fireEvent.click(screen.getByText('覆盖如何更新，哪些仍缺？'));const t=screen.getByRole('table',{name:'更新后的期初事实覆盖名单'});expect(within(t).getAllByRole('row')).toHaveLength(93);fireEvent.change(screen.getByRole('combobox',{name:'期初事实覆盖名单'}),{target:{value:'all'}});expect(within(t).getAllByRole('row')).toHaveLength(151)
})
