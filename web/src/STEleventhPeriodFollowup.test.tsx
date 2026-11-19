import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STEleventhPeriodFollowup} from './STEleventhPeriodFollowup'
import type {EleventhPeriodFollowup} from './STEleventhPeriodFollowup'
import fixture from './__fixtures__/eleventh-period-followup.json'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
import initialStatus from './__fixtures__/initial-status-coverage.json'
import initialEleventh from './__fixtures__/initial-eleventh-four.json'
import type {InitialFour} from './STInitialFour'
afterEach(cleanup)
const data=fixture as EleventhPeriodFollowup
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value}})
const issue=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value}})
it('retains dated uncertainty instead of extending July status to November',()=>{
 render(<STEleventhPeriodFollowup data={data}/>);
 expect(screen.getByText(/目前只核到该公告时点/,{selector:'section > p'})).toBeVisible()
})
it('separates effective agreement from court approval, payment and conditional donations',()=>{
 render(<STEleventhPeriodFollowup data={data}/>);company('002856')
 expect(screen.getByText(/协议按约签章后成立生效/,{selector:'section > p'})).toBeVisible()
 expect(screen.getByText(/捐赠确认分别核/,{selector:'section > p'})).toBeVisible()
 issue('002856-广州一审：合计金额不等于可收款')
 expect(screen.getByText(/诉讼费由原告负担/,{selector:'section > p'})).toBeVisible()
})
it('keeps distinct arbitration cases separate',()=>{
 render(<STEleventhPeriodFollowup data={data}/>);company('002856');issue('002856-铁路仲裁：请求变更不是回款')
 expect(screen.getByText(/不是同一案件/,{selector:'section > p'})).toBeVisible()
 issue('002856-高中园仲裁：与铁路案分别跟踪')
 expect(screen.getByText(/006349/,{selector:'section > p'})).toBeVisible()
})
it('shows a pending application and derived quarterly cash despite positive cumulative cash',()=>{
 render(<STEleventhPeriodFollowup data={data}/>);company('002872');issue('002872-处罚满期后申请，仍需正式批准')
 expect(screen.getByText(/11月18日董事会通过再次申请/,{selector:'section > p'})).toBeVisible()
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 const table=screen.getByRole('table',{name:'季度经营桥接'})
 expect(within(table).getByText('-977.10万元')).toBeVisible()
 expect(within(table).getByText('3,459.26万元')).toBeVisible()
 expect(within(table).getByText('单季为差额推算')).toBeVisible()
})
it('labels scan transcription, restated comparisons and unfinished observations',()=>{
 render(<STEleventhPeriodFollowup data={data}/>);company('002883')
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(screen.getByText(/美芝三季报第2页为扫描原页人工转录/)).toBeVisible()
 company('002872');issue('002872-处罚满期后申请，仍需正式批准')
 fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'))
 expect(screen.getByText(/未满5个市场日，目前1日/)).toBeVisible()
})
it('defaults to the new period while preserving the correct outer date caption',()=>{
 render(<STInitialStatusCoverage data={initialStatus as InitialStatusCoverage} eleventhFour={initialEleventh as InitialFour} eleventhPeriod={data}/>);
 expect(screen.getByRole('region',{name:'第十一批期间判断更新'})).toBeVisible()
 const caption=document.querySelector('#st-initial-status-coverage > p')
 expect(caption).toHaveTextContent('期初到后来')
 expect(caption).toHaveTextContent('2026-11-19')
 expect(caption).not.toHaveTextContent('2026-11-06')
})
