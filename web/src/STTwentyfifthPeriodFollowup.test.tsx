import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STTwentyfifthPeriodFollowup,type TwentyfifthPeriodFollowup} from './STTwentyfifthPeriodFollowup'
import fixture from './__fixtures__/twentyfifth-period-followup.json'
afterEach(cleanup)
const data=fixture as TwentyfifthPeriodFollowup
it('keeps net arithmetic separate from unresolved gross cash',()=>{
 render(<STTwentyfifthPeriodFollowup data={data}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603789'}})
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(screen.getByText(/仅净额累计相减/)).toBeVisible()
 fireEvent.click(screen.getByText('现金转正来自哪里，哪些口径仍待核？'))
 expect(screen.getByText(/不能解释为实际季度负收付款/)).toBeVisible()
 expect(screen.getByRole('table',{name:'经营现金分项累计桥接'})).toBeVisible()
})
it('shows cash alongside loss and negative equity',()=>{
 render(<STTwentyfifthPeriodFollowup data={data}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603825'}})
 expect(screen.getAllByText(/期中负权益未经年度审计/)[0]).toBeVisible()
 fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'))
 expect(screen.getByText('本窗口端点跨渠道一致。')).toBeVisible()
 expect(screen.queryByText('主源值，跨源待核')).toBeNull()
})
