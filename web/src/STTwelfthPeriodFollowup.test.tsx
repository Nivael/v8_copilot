import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STTwelfthPeriodFollowup} from './STTwelfthPeriodFollowup'
import type {TwelfthPeriodFollowup} from './STTwelfthPeriodFollowup'
import fixture from './__fixtures__/twelfth-period-followup.json'
afterEach(cleanup)
const data=fixture as TwelfthPeriodFollowup
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value}})
it('separates completed transfer from annual warning and uses physical PDF pages',()=>{
 render(<STTwelfthPeriodFollowup data={data}/> )
 expect(screen.getByText(/交易完成、过渡期损益和上市公司年度警示分别看/)).toBeVisible()
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(screen.getByRole('link',{name:'半年报主要数据 · 第8页 ↗'})).toHaveAttribute('href',expect.stringContaining('#page=8'))
 expect(within(screen.getByRole('table',{name:'季度经营桥接'})).getByText('单季为差额推算')).toBeVisible()
})
it('does not turn inapplicable reported ratios into company disclosures',()=>{
 render(<STTwelfthPeriodFollowup data={data}/>);company('600053')
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 fireEvent.click(screen.getByText('半年同比：哪些是报告值，哪些只是另算？'))
 expect(within(screen.getByRole('table',{name:'半年同比披露与计算'})).getAllByText('原表不适用')).toHaveLength(3)
 expect(screen.getByRole('link',{name:'三季报现金数据 · 第2页 ↗'})).toHaveAttribute('href',expect.stringContaining('#page=2'))
})
it('updates sale profit to the quarterly disclosure and distinguishes operating cash',()=>{
 render(<STTwelfthPeriodFollowup data={data}/>);company('600079')
 expect(screen.getByText(/原预计损益更新为5.14亿元/)).toBeVisible()
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 const table=screen.getByRole('table',{name:'季度经营桥接'})
 expect(within(table).queryByText('单季为差额推算')).not.toBeInTheDocument()
 expect(within(table).getByText('77,840.59万元')).toBeVisible()
})
it('keeps the initial correction and subsequent arbitration accounting distinct',()=>{
 render(<STTwelfthPeriodFollowup data={data}/>);company('600080')
 expect(screen.getByText(/终局裁决仍有效、预计负债已入损益/)).toBeVisible()
 expect(screen.getByText(/个人处罚不当公司罚款/)).toBeVisible()
 fireEvent.click(screen.getByText('本轮核到哪里，哪些仍缺？'))
 expect(screen.getByText(/新取得19份、复用2份/)).toBeVisible()
 expect(screen.getByText(/期初覆盖保持90\/150/)).toBeVisible()
})
