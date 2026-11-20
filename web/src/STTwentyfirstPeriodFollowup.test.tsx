import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STTwentyfirstPeriodFollowup,type TwentyfirstPeriodFollowup} from './STTwentyfirstPeriodFollowup'
import fixture from './__fixtures__/twentyfirst-period-followup.json'
afterEach(cleanup)
const data=fixture as TwentyfirstPeriodFollowup
const company=(code:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:code}})
it('shows common dates and keeps regulatory progress separate from clearance',()=>{
 render(<STTwentyfirstPeriodFollowup data={data}/>);
 expect(screen.getByRole('table',{name:'四家公司同起止日比较'})).toBeVisible()
 expect(screen.getByText('-14.03%')).toBeVisible()
 expect(screen.getAllByText(/不能直接记为监管验收/)[0]).toBeVisible()
 company('600759');expect(screen.getAllByText(/不能替代新年度独立审计验证/)[0]).toBeVisible()
 company('600818');expect(screen.getAllByText(/798万元仍未收/)[0]).toBeVisible()
})
it('preserves derived cash, non applicable growth and unaudited comparisons',()=>{
 render(<STTwentyfirstPeriodFollowup data={data}/>);company('600889')
 expect(screen.getAllByText(/单季归母同比-47.89%/)[0]).toBeVisible()
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(screen.getByText(/仅中路单季经营现金另算/)).toBeVisible()
 fireEvent.click(screen.getByText('半年同比：哪些是报告值，哪些只是另算？'))
 expect(screen.getAllByText('不适用，未另造增速')).toHaveLength(3)
 company('600818');expect(screen.getByText('单季为差额推算')).toBeVisible()
})
