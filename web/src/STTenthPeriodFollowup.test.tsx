import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STTenthPeriodFollowup} from './STTenthPeriodFollowup'
import type {TenthPeriodFollowup} from './STTenthPeriodFollowup'
import fixture from './__fixtures__/tenth-period-followup.json'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
import initialStatus from './__fixtures__/initial-status-coverage.json'
import initialTenth from './__fixtures__/initial-tenth-four.json'
import type {InitialFour} from './STInitialFour'
afterEach(cleanup)
const data=fixture as TenthPeriodFollowup
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value}})
const issue=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘事项'}),{target:{value}})
it('closes the bond payment task while retaining the replacement debt',()=>{
 render(<STTenthPeriodFollowup data={data}/>);
 expect(screen.getByText(/期初“能否兑付”待办可关闭/,{selector:'section > p'})).toBeVisible();
 expect(screen.getByText(/持有人债权消灭不等于公司总债务归零/,{selector:'section > p'})).toBeVisible();
})
it('keeps the exited company with explained null returns and no fabricated financial table',()=>{
 render(<STTenthPeriodFollowup data={data}/>);company('002731');
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'));
 expect(screen.getByText(/不生成季度桥接，不填零/)).toBeVisible();
 expect(screen.queryByRole('table',{name:'季度经营桥接'})).not.toBeInTheDocument();
 fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'));
 fireEvent.change(screen.getByRole('combobox',{name:'选择期间公告窗口'}),{target:{value:'1225410169'}});
 const table=screen.getByRole('table',{name:'期间公告同窗比较'});
 expect(within(table).getByText('无实际成交端点')).toBeVisible();
 expect(within(table).getByText(/2026-07-03缺收盘记录/)).toBeVisible();
 expect(table).not.toHaveTextContent('NaN');
})
it('separates deposits and a voluntary platform from judicial proceedings',()=>{
 render(<STTenthPeriodFollowup data={data}/>);company('002789');
 expect(screen.getByText(/共缴报名保证金1.2亿元/,{selector:'section > p'})).toBeVisible();
 expect(screen.getByText(/重组中心不是司法机关/,{selector:'section > p'})).toBeVisible();
 issue('建艺-净资产缓冲变薄，申请状态须看日期');
 expect(screen.getByText(/时间口径延伸成11月结论/,{selector:'section > p'})).toBeVisible();
 expect(screen.getByText(/4月28日董事会，原申请公告写4月26日/,{selector:'section > p'})).toBeVisible();
})
it('labels the cash bridge as derived and retains the later application date',()=>{
 render(<STTenthPeriodFollowup data={data}/>);company('002816');
 expect(screen.getByText(/10月30日三季报披露时仍在补材料/,{selector:'section > p'})).toBeVisible();
 fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'));
 const table=screen.getByRole('table',{name:'季度经营桥接'});
 expect(within(table).getByText('单季为差额推算')).toBeVisible();
 expect(within(table).getByText('-2,183.54万元')).toBeVisible();
 expect(screen.getByRole('link',{name:/三季报主要数据/})).toBeVisible();
})
it('does not call complete market windows complete stock observations',()=>{
 render(<STTenthPeriodFollowup data={data}/>);
 fireEvent.click(screen.getByText('本轮核到哪里，哪些仍缺？'));
 expect(screen.getByText(/64个完整市场窗口、11个未满市场窗口，另有18个股票窗口/)).toBeVisible();
})

it('uses the current selected-period cutoff in the outer caption',()=>{
 render(<STInitialStatusCoverage data={initialStatus as InitialStatusCoverage} tenthFour={initialTenth as InitialFour} tenthPeriod={data}/>);
 const caption=document.querySelector('#st-initial-status-coverage > p');
 expect(caption).toHaveTextContent('2026-11-19');
 expect(caption).not.toHaveTextContent('2026-11-06');
})
