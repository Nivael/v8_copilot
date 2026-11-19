import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
import initialStatus from './__fixtures__/initial-status-coverage.json'
import fixture from './__fixtures__/initial-twelfth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('separates proposed acquisition from completed acquisition',()=>{
 render(<STInitialFour data={data} readableAmounts/>);
 expect(screen.getByText(/暂不召开该次股东会/,{selector:'section > p'})).toBeVisible()
 expect(screen.getByText(/86 → 90\/150家/)).toBeVisible()
})
it('keeps the pending price differences visible without replacing actual quotes',()=>{
 render(<STInitialFour data={data}/>);
 const main=screen.getByRole('table',{name:'期初四家风险与同窗表现'})
 expect(within(main).getByText(/15.6483.*15.6738/)).toBeVisible()
 fireEvent.click(screen.getByText('共同价格端点，跨渠道核到哪一步？'))
 const table=screen.getByRole('table',{name:'共同端点缺失与冲突'})
 expect(within(table).getByText('17.29380942981411')).toBeVisible()
 expect(within(table).getByText('17.290')).toBeVisible()
 expect(screen.getAllByText('价格精度或复权口径待核')).toHaveLength(2)
 expect(screen.queryByText(/萃华起点和期末均缺/)).not.toBeInTheDocument()
 expect(screen.getByRole('link',{name:'ST人福 · 另一渠道前复权日线 ↗'})).toHaveAttribute('href',expect.stringContaining('sh600079'))
})
it('switches the common window without removing the unresolved precision boundary',()=>{
 render(<STInitialFour data={data}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}})
 const main=screen.getByRole('table',{name:'期初四家风险与同窗表现'})
 expect(within(main).getByText(/0.7878.*0.8097/)).toBeVisible()
 expect(screen.getByText(/2026-07-31 · 20个交易日/)).toBeVisible()
})
it('defaults to the new initial batch with the correct cutoff',()=>{
 render(<STInitialStatusCoverage data={initialStatus as InitialStatusCoverage} twelfthFour={data}/>);
 expect(screen.getByRole('heading',{name:'审计、归还资金与交易推进，分别解决了什么？'})).toBeVisible()
 expect(document.querySelector('#st-initial-status-coverage > p')).toHaveTextContent('7月3日当时已知 · 后续观察截至 2026-11-19')
})
