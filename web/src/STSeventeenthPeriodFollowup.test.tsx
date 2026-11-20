import {render,screen,fireEvent,within,cleanup} from '@testing-library/react'
import {describe,it,expect,afterEach} from 'vitest'
import {STSeventeenthPeriodFollowup,type SeventeenthPeriodFollowup} from './STSeventeenthPeriodFollowup'
import fixture from './__fixtures__/seventeenth-period-followup.json'
afterEach(cleanup)
const data=fixture as SeventeenthPeriodFollowup
describe('seventeenth period reading',()=>{
 it('shows signing conditions first and retains the three-day par value observation',()=>{
  render(<STSeventeenthPeriodFollowup data={data}/>);
  expect(screen.getAllByText(/中选后的待签约得到推进/)[0]).toBeTruthy()
  fireEvent.click(screen.getByText('低于1元，实际连续了几个交易日？'))
  expect(screen.getByText(/核到连续3个实际交易日/)).toBeTruthy()
  expect(screen.getByText(/2026-11-17：未复权收盘0.920元/)).toBeTruthy()
 })
 it('switches to Sanfang and distinguishes profitable H1 from loss-making Q3',()=>{
  render(<STSeventeenthPeriodFollowup data={data}/>);
  fireEvent.change(screen.getByRole('combobox',{name:'选择期间复盘公司'}),{target:{value:'600370'}})
  fireEvent.click(screen.getByText('半年、第三季度单季和前三季累计，分别怎样？'))
  const table=screen.getByRole('table',{name:'季度经营桥接'});
  expect(within(table).getByText('493.05万元')).toBeTruthy()
  expect(within(table).getByText('-26,683.89万元')).toBeTruthy()
  expect(screen.getAllByText(/不当现金回款/)[0]).toBeTruthy()
 })
 it('keeps incomplete windows explicit rather than filling the future',()=>{
  render(<STSeventeenthPeriodFollowup data={data}/>);
  fireEvent.click(screen.getByText('公告前后，个股、ST与大盘怎样一起变化？'))
  fireEvent.change(screen.getByRole('combobox',{name:'选择期间公告窗口'}),{target:{value:'1225676310'}})
  fireEvent.change(screen.getByRole('combobox',{name:'期间公告观察天数'}),{target:{value:'20'}})
  expect(screen.getByText(/未满20个市场日，目前2日/)).toBeTruthy()
 })
})
