import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STTwentyfourthPeriodFollowup,type TwentyfourthPeriodFollowup} from './STTwentyfourthPeriodFollowup'
import fixture from './__fixtures__/twentyfourth-period-followup.json'
afterEach(cleanup)
const data=fixture as TwentyfourthPeriodFollowup
it('keeps calculated cash distinct when switching companies',()=>{
 render(<STTwentyfourthPeriodFollowup data={data}/>);
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(screen.queryByText('单季为差额推算')).toBeNull()
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603557'}})
 expect(screen.getByText('单季为差额推算')).toBeVisible()
 expect(screen.getAllByText(/首期最后期限未到/)[0]).toBeVisible()
})
it('shows conflicts next to returns and preserves nontraded endpoints',()=>{
 render(<STTwentyfourthPeriodFollowup data={data}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603517'}})
 fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'))
 expect(screen.getByText('主源值，跨源待核')).toBeVisible()
 expect(screen.getByText(/另一渠道同窗为/)).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'1'}})
 expect(screen.getByText('无实际成交端点')).toBeVisible()
 expect(screen.queryByText('主源值，跨源待核')).toBeNull()
 fireEvent.click(screen.getByText('查看事项过程、原件与日期'))
 expect(screen.getAllByRole('link').some(x=>x.getAttribute('href')?.endsWith('#page=3'))).toBe(true)
})
