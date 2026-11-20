import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STFifteenthPeriodFollowup} from './STFifteenthPeriodFollowup'
import type {FifteenthPeriodFollowup} from './STFifteenthPeriodFollowup'
import fixture from './__fixtures__/fifteenth-period-followup.json'
afterEach(cleanup)
const data=fixture as FifteenthPeriodFollowup
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value}})
const issue=(source:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:data.chains.find(c=>c.source===source)!.chain}})
it('keeps old-year reclassification separate from new loss and blank ratios',()=>{
 render(<STFifteenthPeriodFollowup data={data}/> )
 expect(screen.getAllByText(/不当2026新发生亏损或现金流出/)[0]).toBeVisible()
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 fireEvent.click(screen.getByText('半年同比：哪些是报告值，哪些只是另算？'))
 expect(within(screen.getByRole('table',{name:'半年同比披露与计算'})).getAllByText('原表空白')).toHaveLength(3)
})
it('separates removal of star from full removal and delivery from execution completion',()=>{
 render(<STFifteenthPeriodFollowup data={data}/>);company('600238')
 expect(screen.getAllByText(/不是全部摘帽/)[0]).toBeVisible()
 issue('1225469364');expect(screen.getAllByText(/签约不证明交货签收或法院结案/)[0]).toBeVisible()
})
it('keeps registered assets separate from cash and leaves missing approval evidence open',()=>{
 render(<STFifteenthPeriodFollowup data={data}/>);company('600239')
 expect(screen.getAllByText(/未证明全部现金收到或减资完成/)[0]).toBeVisible()
 company('600243');fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:data.chains.find(c=>c.chain.startsWith('600243-申请'))!.chain}})
 expect(screen.getAllByText(/未找到不能等同从未发生/)[0]).toBeVisible()
})
