import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
import initialStatus from './__fixtures__/initial-status-coverage.json'
import fixture from './__fixtures__/initial-thirteenth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value}})
it('keeps punishment conditions separate from corrected accounts',()=>{
 render(<STInitialFour data={data}/>);
 expect(screen.getByText(/90 → 94\/150家/)).toBeVisible()
 expect(screen.getByText(/处罚警示仍有独立门槛/)).toBeVisible()
 expect(screen.getByText(/不从ST实施日倒推自动摘帽日/)).toBeVisible()
})
it('does not treat repaid principal and interest as an effective internal control audit',()=>{
 render(<STInitialFour data={data}/>);company('600107')
 expect(screen.getByText(/会计师未做期后内控审计，无法确认整改有效/)).toBeVisible()
 expect(screen.getByText(/不证明当日交易前已知/)).toBeVisible()
})
it('keeps litigation unresolved despite the board accounting statement',()=>{
 render(<STInitialFour data={data}/>);company('600119')
 expect(screen.getByText(/诉讼仍无生效判决/)).toBeVisible()
 fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'))
 expect(screen.getByRole('link',{name:/长江投资.*专项说明 · 第3页/})).toHaveAttribute('href',expect.stringContaining('#page=3'))
})
it('switches a common window and defaults the outer view to the latest verified batch',()=>{
 render(<STInitialStatusCoverage data={initialStatus as InitialStatusCoverage} thirteenthFour={data}/>);
 expect(document.querySelector('#st-initial-status-coverage > p')).toHaveTextContent('2026-11-19')
 fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}})
 expect(screen.getByText(/2026-07-31 · 20个交易日/)).toBeVisible()
 expect(within(screen.getByRole('table',{name:'期初四家风险与同窗表现'})).getByText('+1.42%')).toBeVisible()
})
