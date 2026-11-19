import {render,screen,fireEvent,within,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
import type {RuiheProcess} from './STRuiheProcess'
import next from './__fixtures__/initial-next-four.json'
import old from './__fixtures__/initial-four.json'
import baseline from './__fixtures__/initial-status-coverage.json'
import ruihe from './__fixtures__/ruihe-process.json'
afterEach(cleanup)
const data=next as InitialFour
it('shows four distinct initial stages and the same 20/93-day comparisons',()=>{
 render(<STInitialFour data={data}/>);expect(screen.getByText(/46 → 50\/150家/)).toBeTruthy();expect(screen.getByText(/仍缺100家/)).toBeTruthy()
 expect(screen.getByRole('table',{name:'期初四家风险与同窗表现'})).toHaveTextContent('正式重整受理')
 expect(screen.getByText('-36.07%')).toBeTruthy();fireEvent.change(screen.getByLabelText('期初四家比较窗口'),{target:{value:'early20'}});expect(screen.getByText('+1.64%')).toBeTruthy()
})
it('keeps financial qualified opinion separate from the internal-control opinion',()=>{
 render(<STInitialFour data={data}/>);fireEvent.change(screen.getByLabelText('选择公司核对期初原件'),{target:{value:'000669'}});expect(screen.getByText(/财报却仍为保留意见/)).toBeTruthy();fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/不能用内控意见覆盖/)).toBeTruthy()
})
it('keeps visual extraction limits and main-account versus subsidiary-account scope explicit',()=>{
 render(<STInitialFour data={data}/>);fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));expect(screen.getByText(/无法有效提取正文，已看渲染页/)).toBeTruthy();expect(screen.getByText(/部分子公司账户冻结/)).toBeTruthy()
})
it('retains one hundred gaps and the complete fixed cohort without adding certification',()=>{
 render(<STInitialFour data={data}/>);fireEvent.click(screen.getByText('覆盖如何更新，哪些仍缺？'));const table=screen.getByRole('table',{name:'更新后的期初事实覆盖名单'});expect(within(table).getAllByRole('row')).toHaveLength(101)
 fireEvent.change(screen.getByLabelText('期初事实覆盖名单'),{target:{value:'all'}});expect(within(table).getAllByRole('row')).toHaveLength(151)
})
it('defaults to new coverage when it arrives and retains the previous batch as a selectable view',()=>{
 const props={data:baseline as InitialStatusCoverage,ruihe:ruihe as RuiheProcess,four:old as InitialFour};const {rerender}=render(<STInitialStatusCoverage {...props}/>);expect(screen.getByText(/42 → 46\/150家/)).toBeTruthy()
 rerender(<STInitialStatusCoverage {...props} nextFour={data}/>);expect(screen.getByText(/46 → 50\/150家/)).toBeTruthy()
 fireEvent.change(screen.getByLabelText('期初专题阅读目的'),{target:{value:'four'}});expect(screen.getByText(/42 → 46\/150家/)).toBeTruthy()
 fireEvent.change(screen.getByLabelText('期初专题阅读目的'),{target:{value:'next'}});expect(screen.getByText(/46 → 50\/150家/)).toBeTruthy()
})
