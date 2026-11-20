import {cleanup,render,screen,fireEvent,within} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {MarketBreadthSequence} from './MarketBreadthSequence'
afterEach(cleanup)
it('retains the positive counterexample and keeps future outcomes retrospective',()=>{
 render(<MarketBreadthSequence/>);expect(screen.getByText('+1.61%')).toBeVisible();expect(screen.getByText('-3.76%')).toBeVisible()
 expect(screen.getByText(/仅凭这两段，不能得出统一的减仓效果/)).toBeVisible()
 expect(screen.getByRole('table',{name:'全部两次提示均保留，随后行情为事后对照'})).toBeVisible()
})
it('date inspection has only then-and-earlier rows and does not add repeated signals',()=>{
 render(<MarketBreadthSequence/>);fireEvent.click(screen.getByText('选一天，看截至当日已经出现了什么'))
 const select=screen.getByRole('combobox',{name:'历史广度观察日'})
 const options=within(select).getAllByRole('option');const value=options.find(o=>o.textContent==='2026-09-11')!.getAttribute('value')!
 fireEvent.change(select,{target:{value}})
 const table=screen.getByRole('table',{name:'所选日期及之前最多三个交易日'});expect(within(table).getAllByRole('row')).toHaveLength(4)
 expect(within(table).getByText('2026-09-09')).toBeVisible();expect(within(table).queryByText('2026-09-14')).not.toBeInTheDocument()
 expect(screen.getByText(/这是本段在覆盖范围内的第三日提示/)).toBeVisible()
 fireEvent.change(select,{target:{value:options[0].getAttribute('value')}})
 expect(within(table).getAllByRole('row')).toHaveLength(2)
})
