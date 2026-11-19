import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STSeventhPeriodFollowup} from './STSeventhPeriodFollowup'
import type {SeventhPeriodFollowup} from './STSeventhPeriodFollowup'
import fixture from './__fixtures__/seventh-period-followup.json'
afterEach(cleanup)
const data=fixture as SeventhPeriodFollowup
it('separates one released subsidiary account from remaining parent freeze',()=>{
 render(<STSeventhPeriodFollowup data={data}/>);expect(screen.getByText(/子公司专户2220.37元解除冻结/, {selector:"section > p"})).toBeVisible();expect(screen.getByText(/上市公司另一个募资专户仍冻结约1688.78万元/)).toBeVisible()
})
it('keeps outgoing and incoming settlement money separate',()=>{
 render(<STSeventhPeriodFollowup data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:'棕榈-收回工程款'}});expect(screen.getByText(/上市公司为收款方/)).toBeVisible();expect(screen.getByText(/未证明已到账/, {selector:"section > p"})).toBeVisible();fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:'棕榈-梅州三案支付工程款'}});expect(screen.getByText(/子公司梅州棕沅为付款方/)).toBeVisible()
})
it('shows five notices as one unfinished acquisition',()=>{
 render(<STSeventhPeriodFollowup data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'002501'}});expect(screen.getByText(/不是5次独立成功/)).toBeVisible();fireEvent.click(screen.getByText('查看事项过程、原件与日期'));expect(screen.getAllByText(/尚未签署正式协议/)).toHaveLength(5)
})
it('retains unfinished long windows and corrected July baseline',()=>{
 render(<STSeventhPeriodFollowup data={data}/>);fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'));fireEvent.change(screen.getByRole('combobox',{name:'选择期间公告窗口'}),{target:{value:'1225409315'}});fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'1'}});expect(screen.getByText(/2026-07-03收盘 → 2026-07-06/)).toBeVisible();fireEvent.change(screen.getByRole('combobox',{name:'选择期间公告窗口'}),{target:{value:'1225665354'}});fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'20'}});expect(screen.getByText(/未满20日/)).toBeVisible()
})
it('does not turn narrowed losses into profit',()=>{
 render(<STSeventhPeriodFollowup data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'002485'}});expect(screen.getByText(/改善比例不等于正利润或正现金/, {selector:"section > p"})).toBeVisible()
})
