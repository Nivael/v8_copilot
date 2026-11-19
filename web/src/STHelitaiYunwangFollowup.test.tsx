import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STHelitaiYunwangFollowup} from './STHelitaiYunwangFollowup'
import type {HelitaiYunwangFollowup} from './STHelitaiYunwangFollowup'
import fixture from './__fixtures__/helitai-yunwang-followup.json'
afterEach(cleanup)
const data=fixture as HelitaiYunwangFollowup
it('closes only the specific rent payment and account task',()=>{
 render(<STHelitaiYunwangFollowup data={data}/>);expect(screen.getByText(/关闭该案付款及对应账户待办/)).toHaveTextContent('对应涉诉银行账号已解冻');expect(screen.getByRole('heading',{name:'先更新判断：某案解冻之外，基本户又出现新增冻结'})).toBeVisible()
})
it('reopens a withdrawn case without saying the claim was permanently removed',()=>{
 render(<STHelitaiYunwangFollowup data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'云网案件事项链'}),{target:{value:'lead_intelligent'}});expect(screen.getByText(/收到重新起诉文件/)).toBeVisible()
})
it('preserves raw rows and subtotal conflict without certifying one total',()=>{
 render(<STHelitaiYunwangFollowup data={data}/>);fireEvent.click(screen.getByText('逐行核冻结金额、主体与公告小计'));const t=screen.getByRole('table',{name:'冻结表逐行与小计冲突'});expect(within(t).getByText('11,475,904.50')).toBeVisible();expect(within(t).getByText('9,320,369.50')).toBeVisible();expect(screen.getByText(/没有认证“正确总额”/)).toBeVisible()
})
it('shows unfinished windows as observed partial periods',()=>{
 render(<STHelitaiYunwangFollowup data={data}/>);fireEvent.click(screen.getByText('同一份公告多个案件，价格窗口只观察一次'));fireEvent.change(screen.getByRole('combobox',{name:'云网公告后观察天数'}),{target:{value:'20'}});expect(screen.getByText(/尚未满20日/)).toBeVisible()
})
it('does not count four recurring notices as four independent repairs',()=>{
 render(<STHelitaiYunwangFollowup data={data}/>);fireEvent.change(screen.getByRole('combobox',{name:'选择后续待办公司'}),{target:{value:'helitai'}});expect(screen.getByText(/四次重述不增加独立经验验证次数/)).toBeVisible();expect(screen.getByRole('link',{name:'2026-10-21 ↗'})).toBeVisible();expect(screen.getByText('2026-10-20')).toBeVisible()
})
