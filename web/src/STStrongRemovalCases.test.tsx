import {render,screen,fireEvent,within,cleanup} from '@testing-library/react'
import {describe,it,expect,afterEach} from 'vitest'
import {STStrongRemovalCases} from './STStrongRemovalCases'
import raw from './__fixtures__/strong-removal-cases.json'
import type {RegimeStrongRemovalCases} from './stRegimeTypes'
afterEach(cleanup)
const fixture=raw as unknown as RegimeStrongRemovalCases
describe('strong removal case explanations',()=>{
 it('answers the question and compares stock, market and ST using explicit dates',()=>{
  render(<STStrongRemovalCases data={fixture}/>);expect(screen.getByRole('heading',{name:'摘帽后涨得强，经营就已经修复了吗？'})).toBeVisible()
  expect(screen.getByText('+46.39%')).toBeVisible();expect(screen.getByText('+24.82%')).toBeVisible();expect(screen.getByText('-25.21%')).toBeVisible()
  fireEvent.change(screen.getByRole('combobox',{name:'强势案例行情窗口'}),{target:{value:'40'}})
  expect(screen.getByText('+20.96%')).toBeVisible();expect(screen.getByText('2026-07-21 → 2026-09-15')).toBeVisible()
 })
 it('shows single cash improvement separately from cumulative outflow and cites physical pages',()=>{
  render(<STStrongRemovalCases data={fixture}/>);fireEvent.click(screen.getByText('神雾节能：改善在哪里，约束还在哪里？'))
  expect(screen.getByText(/第三季单季经营现金净额.*122.73.*累计仍为-4,745.68/)).toBeVisible()
  expect(screen.getAllByText(/两份实际财报都晚于摘帽/).some(x=>x.closest('details')?.open)).toBe(true)
  const link=screen.getAllByRole('link',{name:'原件第2页 ↗'}).find(a=>a.getAttribute('href')?.includes('b4df2706'))
  expect(link?.getAttribute('href')).toContain('#page=2')
  expect(screen.getByText(/这是股东之间的持股变化，不是上市公司收到回款/)).toBeVisible()
  expect(screen.getByText(/截至三季报披露仍未收到/)).toBeVisible()
  expect(screen.getByText(/尚未实缴.*不把业务名称当已兑现利润/)).toBeVisible()
 })
 it('keeps original and revised half reports and warns against mixed-period subtraction',()=>{
  render(<STStrongRemovalCases data={fixture}/>);fireEvent.click(screen.getByText('东晶电子：改善在哪里，约束还在哪里？'));fireEvent.click(screen.getByText('东晶半年更正：哪些数字变了，哪些没变？'))
  expect(screen.getByText('8月25日原披露')).toBeVisible();expect(screen.getByText('10月29日更正后')).toBeVisible()
  expect(screen.getByText(/若错用旧半年扣非.*-164.18.*-1,119.41/)).toBeVisible()
  expect(within(screen.getByRole('region',{name:'强势摘帽案例与经营变化'})).getByText(/未晋级通用规律/)).toBeVisible()
 })
 it('does not invent financial evidence for old snapshots',()=>{const {container}=render(<STStrongRemovalCases data={null}/>);expect(container).toBeEmptyDOMElement()})
})
