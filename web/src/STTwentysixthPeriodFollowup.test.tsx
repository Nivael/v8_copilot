import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STTwentysixthPeriodFollowup,type TwentysixthPeriodFollowup} from './STTwentysixthPeriodFollowup'
import fixture from './__fixtures__/twentysixth-period-followup.json'
afterEach(cleanup)
it('withholds conflicting stock returns while retaining market background and both raw values',()=>{
 render(<STTwentysixthPeriodFollowup data={fixture as TwentysixthPeriodFollowup}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603869'}})
 fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'))
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间公告窗口'}),{target:{value:'1225426487'}})
 expect(within(screen.getByRole('table',{name:'期间公告同窗比较'})).getByText('报价口径冲突，暂不认证收益')).toBeVisible()
 expect(screen.getByText(/主源未认证值为/)).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'20'}})
 expect(screen.getByText('报价口径冲突，暂不认证收益')).toBeVisible()
})
it('keeps procedure separate from fund payment and parent cash from consolidated cash',()=>{
 render(<STTwentysixthPeriodFollowup data={fixture as TwentysixthPeriodFollowup}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603869'}})
 expect(screen.getAllByText(/分期缴付/)[0]).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'603843'}})
 const option=fixture.chains.find(c=>c.subject==='正平现金转正，经营风险是否已解除？')!
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:option.chain}})
 expect(screen.getByText(/母公司单独仍净流出/)).toBeVisible()
})

it('states the actual direct versus calculated scope for this cohort',()=>{
 render(<STTwentysixthPeriodFollowup data={fixture as TwentysixthPeriodFollowup}/>);
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(screen.getByText(/16项中15项直接值/)).toBeVisible()
 expect(screen.getByText('单季为差额推算')).toBeVisible()
})
