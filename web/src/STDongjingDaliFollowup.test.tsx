import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STDongjingDaliFollowup} from './STDongjingDaliFollowup'
import type {DongjingDaliFollowup} from './STDongjingDaliFollowup'
import fixture from './__fixtures__/dongjing-dali-followup.json'
afterEach(cleanup)
const data=fixture as DongjingDaliFollowup
it('compares short and later paths with their own ST and market windows',()=>{
 render(<STDongjingDaliFollowup data={data}/>);const t=screen.getByRole('table',{name:'两家摘帽后同窗表现'});expect(within(t).getByText('+32.71%')).toBeVisible();expect(within(t).getByText('+0.47%')).toBeVisible();fireEvent.change(screen.getByRole('combobox',{name:'两家摘帽后观察窗口'}),{target:{value:'first_resume_to_latest'}});expect(within(t).getByText('-19.94%')).toBeVisible();expect(within(t).getByText('+5.72%')).toBeVisible()
})
it('separates single quarter profit and cash direction',()=>{
 render(<STDongjingDaliFollowup data={data}/>);const t=screen.getByRole('table',{name:'两家公司第三季单季经营对照'});expect(within(t).getByText('-308.27万元')).toBeVisible();expect(within(t).getByText('876.28万元')).toBeVisible();expect(within(t).getByText('-4044.22万元')).toBeVisible()
})
it('retains original and corrected half-year figures at their disclosure dates',()=>{
 render(<STDongjingDaliFollowup data={data}/>);fireEvent.click(screen.getByText('东晶半年报更正：保留当时版本，再算第三季度'));expect(screen.getByText(/8月25日原半年摘要/)).toHaveTextContent('-14304120.70元');expect(screen.getByText(/若误用旧扣非数/)).toHaveTextContent('-11194144.47元')
})
it('shows exact figures, auditable source links and remaining boundaries on demand',()=>{
 render(<STDongjingDaliFollowup data={data}/>);fireEvent.click(screen.getByText('财务精确值、现金桥与来源按需核对'));expect(screen.getByText(/半年度摘要的/)).toBeVisible();expect(screen.getAllByRole('link')).toHaveLength(10);expect(screen.getByText(/期初覆盖仍62\/150/)).toBeVisible();expect(screen.getByText(/后续扣非转为盈利/)).toBeVisible()
})
