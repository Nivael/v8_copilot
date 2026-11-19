import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STNinthPeriodFollowup} from './STNinthPeriodFollowup'
import type {NinthPeriodFollowup} from './STNinthPeriodFollowup'
import fixture from './__fixtures__/ninth-period-followup.json'
afterEach(cleanup)
const data=fixture as NinthPeriodFollowup
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value}})
const issue=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value}})
it('updates the removal judgment and separates pre-removal losses from later losses',()=>{
 render(<STNinthPeriodFollowup data={data}/>);expect(screen.getByText(/期初“尚待核准”这一待办可关闭/, {selector:'section > p'})).toBeVisible();fireEvent.click(screen.getByText('整段跌幅，发生在摘帽前还是摘帽后？'));const table=screen.getByRole('table',{name:'东易摘帽分段同窗比较'});expect(within(table).getByText('-21.58%')).toBeVisible();expect(within(table).getByText('-9.97%')).toBeVisible();expect(within(table).getByText('-22.04%')).toBeVisible();expect(screen.getByText(/首日段跨两个市场日/)).toBeVisible()
})
it('preserves the halted announcement-day stock return as missing',()=>{
 render(<STNinthPeriodFollowup data={data}/>);fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'));fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'1'}});const table=screen.getByRole('table',{name:'期间公告同窗比较'});expect(within(table).getByText('无实际成交端点')).toBeVisible();expect(within(table).getByText(/2026-07-17无实际成交收盘/)).toBeVisible();expect(table).not.toHaveTextContent('NaN')
})
it('labels quarterly operating cash as derived while retaining reported profit',()=>{
 render(<STNinthPeriodFollowup data={data}/>);fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'));const table=screen.getByRole('table',{name:'季度经营桥接'});expect(within(table).getByText('单季为差额推算')).toBeVisible();expect(within(table).getByText('-12,494.93万元')).toBeVisible();expect(within(table).getByText('-3,685.67万元')).toBeVisible()
})
it('does not turn a remand into a final release and retains the receipt-date conflict',()=>{
 render(<STNinthPeriodFollowup data={data}/>);company('002694');expect(screen.getByRole('heading',{name:'股价上涨，诉讼和经营压力消失了吗？'})).toBeVisible();expect(screen.getByText(/不是终局认定不承担责任/, {selector:'section > p'})).toBeVisible();expect(screen.getByText(/8月5日收到，9月表称8月6日/, {selector:'section > p'})).toBeVisible()
})
it('keeps Jiajia recovery and source classification differences visible',()=>{
 render(<STNinthPeriodFollowup data={data}/>);company('002650');expect(screen.getByRole('heading',{name:'收到拍卖款，是否等于赔偿债权已收回？'})).toBeVisible();expect(screen.getByText(/损失赔偿款和拍卖款不是同笔回款/, {selector:'section > p'})).toBeVisible();expect(screen.getByText(/与旧会计师说明称形成资金占用的分类不同/, {selector:'section > p'})).toBeVisible()
})
it('keeps a withdrawn petition open to later evidence and preserves the auction-year conflict',()=>{
 render(<STNinthPeriodFollowup data={data}/>);company('002719');expect(screen.getByText(/不能把8月撤回当债务已结清/, {selector:'section > p'})).toBeVisible();issue('麦趣-两次流拍不是处置回款');expect(screen.getByText(/两处写2025年8月25日/, {selector:'section > p'})).toBeVisible();expect(screen.getByText(/不写成资产已售出/, {selector:'section > p'})).toBeVisible()
})
