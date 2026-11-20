import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STTwentiethPeriodFollowup,type TwentiethPeriodFollowup} from './STTwentiethPeriodFollowup'
import fixture from './__fixtures__/twentieth-period-followup.json'
afterEach(cleanup)
const data=fixture as TwentiethPeriodFollowup
const company=(code:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:code}})
it('keeps partial receipts and limited compliance review distinct',()=>{
 render(<STTwentiethPeriodFollowup data={data}/>);
 expect(screen.getAllByText(/部分回收与违约并存/)[0]).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:data.chains[1].chain}})
 expect(screen.getAllByText(/不是年度内控消除结论/)[0]).toBeVisible()
})
it('preserves restated comparisons, shareholder scope, and unresolved audit evidence',()=>{
 render(<STTwentiethPeriodFollowup data={data}/>);company('600734')
 expect(screen.getAllByText(/按重述比较期下降22.75%/)[0]).toBeVisible()
 company('600735');fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value:data.chains[4].chain}})
 expect(screen.getAllByText(/不是上市公司自身重整获批/)[0]).toBeVisible()
 company('600745');expect(screen.getAllByText(/无法表示意见所涉事项尚未消除/)[0]).toBeVisible()
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
 expect(screen.getByRole('table',{name:'季度经营桥接'})).toBeVisible()
 expect(screen.getByText(/4项单季经营现金另算/)).toBeVisible()
})
