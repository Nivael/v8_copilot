import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STYigouSettlement} from './STYigouSettlement'
import type {YigouSettlement} from './STYigouSettlement'
import fixture from './__fixtures__/yigou-settlement.json'
afterEach(cleanup)
const data=fixture as YigouSettlement
it('separates cumulative profit, core loss and latest quarterly cash',()=>{
 render(<STYigouSettlement data={data}/>);const t=screen.getByRole('table',{name:'易购利润扣非与现金对照'})
 expect(within(t).getByText('+0.54')).toBeVisible();expect(within(t).getByText('-35.00')).toBeVisible();expect(within(t).getByText('-1.19')).toBeVisible()
 expect(screen.getByText(/三列分别是半年/)).toHaveTextContent('两份报告均未经审计')
 fireEvent.click(screen.getByText('这些数字怎样核对？'));expect(screen.getByText(/第三季度经营现金流由前三季累计减上半年/)).toHaveTextContent('不能再把其中债务重组损益加一次')
})
it('keeps Yunxiang and offshore settlement distinct from Yunchuang approval',()=>{
 render(<STYigouSettlement data={data}/>);fireEvent.click(screen.getByText('看审批原件与容易混淆的三件事'))
 expect(screen.getByText(/半年报披露的是另一项流动性支持展期/)).toBeVisible()
 expect(screen.getByText(/半年报称该笔借款在报告期内结清/)).toHaveTextContent('不证明云创门店和解结清')
 expect(screen.getByText(/没有定位完整履约链/)).toHaveTextContent('不能当成后续文件不存在')
 expect(screen.getByRole('link',{name:/年度股东会决议公告 · 第4页/})).toHaveAttribute('href',expect.stringContaining('1225388521.PDF#page=4'))
})
it('uses next market day for weekend release and preserves unfinished 20-day window',()=>{
 render(<STYigouSettlement data={data}/>);fireEvent.click(screen.getByText('财报披露前后，同一窗口怎样变化？'))
 const t=screen.getByRole('table',{name:'易购财报披露观察窗口'});expect(within(t).getByText('2026-08-28 → 2026-08-31')).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择财报'}),{target:{value:'1225638414'}})
 expect(within(t).getAllByText('窗口未满')).toHaveLength(3);expect(within(t).getByText('2026-10-28 → 未满')).toBeVisible()
})
it('shows five monthly windows and honestly counts reused inputs',()=>{
 render(<STYigouSettlement data={data}/>);fireEvent.click(screen.getByText('逐月比较个股、ST与大盘'))
 expect(within(screen.getByRole('table',{name:'易购逐月同窗行情'})).getAllByRole('row')).toHaveLength(6)
 fireEvent.click(screen.getByText('核验范围与尚未解决的问题'));expect(screen.getByText(/新增2份205页财报/)).toHaveTextContent('复用3份15页旧公告')
 expect(screen.getByText(/新增2份205页财报/)).toHaveTextContent('新增报价请求为0')
})
it('omits unavailable packet',()=>{const {container}=render(<STYigouSettlement/>);expect(container).toBeEmptyDOMElement()})
