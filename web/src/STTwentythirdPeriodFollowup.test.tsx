import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STTwentythirdPeriodFollowup,type TwentythirdPeriodFollowup} from './STTwentythirdPeriodFollowup'
import fixture from './__fixtures__/twentythird-period-followup.json'
afterEach(cleanup)
const data=fixture as TwentythirdPeriodFollowup
it('separates computed cash and direct values when companies change',()=>{
 render(<STTwentythirdPeriodFollowup data={data}/>);
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(screen.getByText('单季为差额推算')).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603377'}})
 expect(screen.queryByText('单季为差额推算')).toBeNull()
 expect(screen.getAllByText(/仍为预重整/)[0]).toBeDefined()
})
it('retains unfinished horizons and links original pages',()=>{
 render(<STTwentythirdPeriodFollowup data={data}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603378'}})
 fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'))
 fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'20'}})
 expect(screen.getByText(/未满20个市场日，目前9日/)).toBeVisible()
 fireEvent.click(screen.getByText('查看事项过程、原件与日期'))
 expect(screen.getAllByRole('link').some(x=>x.getAttribute('href')?.endsWith('#page=1'))).toBe(true)
})
