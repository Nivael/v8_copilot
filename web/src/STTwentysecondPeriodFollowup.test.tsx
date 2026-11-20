import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STTwentysecondPeriodFollowup,type TwentysecondPeriodFollowup} from './STTwentysecondPeriodFollowup'
import fixture from './__fixtures__/twentysecond-period-followup.json'
afterEach(cleanup)
const data=fixture as TwentysecondPeriodFollowup
const company=(code:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:code}})
it('updates program approvals while retaining audit and collection limits',()=>{
 render(<STTwentysecondPeriodFollowup data={data}/>);
 expect(screen.getAllByText(/两项待表决可以关闭/)[0]).toBeVisible()
 company('601010');expect(screen.getAllByText(/总已执行109.63万元中公司43.14万元/)[0]).toBeVisible()
 company('603008');expect(screen.getAllByText(/下降不等于回收/)[0]).toBeVisible()
 expect(screen.getByRole('table',{name:'四家公司同起止日比较'})).toBeVisible()
})
it('shows three material bridge differences without a penny-rounding claim',()=>{
 render(<STTwentysecondPeriodFollowup data={data}/>);company('601718')
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:data.chains[4].chain}})
 expect(screen.getAllByText(/完整调节表/)[0]).toBeDefined()
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(screen.getAllByText('报告值与原半年差额不一致')).toHaveLength(3)
 fireEvent.click(screen.getAllByText('衔接差异：查看报告值与原半年差额')[0])
 expect(screen.getByText(/40672.56元/)).toBeVisible()
 expect(screen.queryByText(/0.01元差异/)).toBeNull()
})
