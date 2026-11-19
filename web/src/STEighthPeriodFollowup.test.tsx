import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STEighthPeriodFollowup} from './STEighthPeriodFollowup'
import type {EighthPeriodFollowup} from './STEighthPeriodFollowup'
import fixture from './__fixtures__/eighth-period-followup.json'
afterEach(cleanup)
const data=fixture as EighthPeriodFollowup
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value}})
const issue=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value}})
it('shows paid trust funds with spending restrictions and no double counting',()=>{
 render(<STEighthPeriodFollowup data={data}/>);expect(screen.getByText(/5亿元已足额支付/, {selector:'section > p'})).toBeVisible();expect(screen.getByText(/不是全部重整投资款已进公司可自由使用/, {selector:"section > p"})).toBeVisible();fireEvent.click(screen.getByText('查看事项过程、原件与日期'));expect(screen.getByText(/2026-10-15 · 已披露/)).toBeVisible()
})
it('keeps lead investor changes separate from other members and actual payment',()=>{
 render(<STEighthPeriodFollowup data={data}/>);issue('英飞-11月补充协议二');expect(screen.getByText(/60个月锁定/, {selector:'section > p'})).toBeVisible();expect(screen.getByText(/不能把其他成员/, {selector:"section > p"})).toBeVisible();fireEvent.click(screen.getByText('查看事项过程、原件与日期'));expect(screen.getByText(/36/)).toBeVisible()
})
it('retains the director dissent alongside improved cash flow',()=>{
 render(<STEighthPeriodFollowup data={data}/>);company('002630');expect(screen.getByText(/同比增7.67%/, {selector:"section > p"})).toBeVisible();expect(screen.getByText(/董事谢应来明确无法保证/, {selector:"section > p"})).toBeVisible()
})
it('does not present shrinking cash outflow as inflow and preserves unconfirmed document date',()=>{
 render(<STEighthPeriodFollowup data={data}/>);company('002581');expect(screen.getByText(/现金流出收窄不等于净流入/, {selector:"section > p"})).toBeVisible();fireEvent.click(screen.getByText('查看事项过程、原件与日期'));expect(screen.getByText(/文件落款未确认，采用正式披露日/)).toBeVisible()
})
it('keeps auditor evidence expandable without conflating accounting scopes',()=>{
 render(<STEighthPeriodFollowup data={data}/>);company('002634');expect(screen.getByText(/与期初合并总净资产不同口径/, {selector:"section > p"})).toBeVisible();fireEvent.click(screen.getByText('查看事项过程、原件与日期'));expect(screen.getAllByRole('link',{name:/专项/}).length).toBeGreaterThan(0)
})
it('shows unfinished November windows and the one-day July observation',()=>{
 render(<STEighthPeriodFollowup data={data}/>);fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'));fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'20'}});expect(screen.getByText(/未满20日/)).toBeVisible();fireEvent.change(screen.getByRole('combobox',{name:'选择期间公告窗口'}),{target:{value:'1225420221'}});fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'1'}});expect(screen.getByText(/2026-07-10收盘 → 2026-07-13/)).toBeVisible();expect(screen.getByRole('table',{name:'期间公告同窗比较'})).toBeVisible()
})
