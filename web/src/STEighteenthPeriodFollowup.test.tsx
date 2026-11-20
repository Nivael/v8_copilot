import {afterEach,it,expect} from 'vitest'
import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {STEighteenthPeriodFollowup,type EighteenthPeriodFollowup} from './STEighteenthPeriodFollowup'
import fixture from './__fixtures__/eighteenth-period-followup.json'
afterEach(cleanup)
const data=fixture as EighteenthPeriodFollowup
const company=(v:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:v}})
it('updates formal removal without closing separate operating and legal questions',()=>{
 render(<STEighteenthPeriodFollowup data={data}/>);
 expect(screen.getAllByText(/26日撤销生效/)[0]).toBeVisible()
 expect(screen.getAllByText(/利润总额约8192.74万元/)[0]).toBeVisible()
 fireEvent.click(screen.getByText('把行情分段，反转发生在哪一段？'))
 expect(screen.getByText(/获批前收盘至8月26日撤销生效日下跌4.84%/)).toBeVisible()
})
it('separates two regulators and the two equity bases',()=>{
 render(<STEighteenthPeriodFollowup data={data}/>);company('600476')
 expect(screen.getAllByText(/证监会立案未收到结论/)[0]).toBeVisible()
 company('600537');fireEvent.click(screen.getByText('公告与财报的两个净资产数字为何不同？'))
 expect(screen.getByText(/不同归属口径，不当来源冲突/)).toBeVisible()
 expect(screen.getByRole('link',{name:'资产负债表权益原页 ↗'})).toHaveAttribute('href',expect.stringContaining('#page=9'))
})
it('does not fill the suspended removal-announcement endpoint',()=>{
 render(<STEighteenthPeriodFollowup data={data}/>);
 fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'))
 fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'1'}})
 expect(screen.getByText(/2026-08-25缺收盘记录/)).toBeVisible()
})
