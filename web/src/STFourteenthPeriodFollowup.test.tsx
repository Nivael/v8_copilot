import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STFourteenthPeriodFollowup} from './STFourteenthPeriodFollowup'
import type {FourteenthPeriodFollowup} from './STFourteenthPeriodFollowup'
import fixture from './__fixtures__/fourteenth-period-followup.json'
afterEach(cleanup)
const data=fixture as FourteenthPeriodFollowup
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value}})
it('shows new judgments and keeps recurring profit understandable',()=>{
 render(<STFourteenthPeriodFollowup data={data}/>);company('600169')
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(within(screen.getByRole('table',{name:'季度经营桥接'})).getByText('扣非净利润')).toBeVisible()
 expect(screen.getByText(/太重同比采用同一控制合并调整后口径/)).toBeVisible()
})
it('makes original data conflicts inspectable',()=>{
 render(<STFourteenthPeriodFollowup data={data}/>);company('600165')
 fireEvent.click(screen.getByText('数据有冲突：净资产和诉请金额怎样处理？'))
 expect(screen.getByText(/半年报第6页上年末归母净资产/)).toBeVisible()
 expect(screen.getByRole('link',{name:'冲突原件第33页 ↗'})).toHaveAttribute('href',expect.stringContaining('#page=33'))
})
it('keeps insurance distinct from cash and two low price intervals separate',()=>{
 render(<STFourteenthPeriodFollowup data={data}/>);company('600180')
 expect(screen.getAllByText(/1000万元报名保证金以投标保证保险保单方式/)[0]).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:data.chains.find(c=>c.source==='1225668568')!.chain}})
 expect(screen.getAllByText(/12日至19日连续6个交易日/)[0]).toBeVisible()
})
