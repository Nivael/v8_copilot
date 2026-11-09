import {render,screen,fireEvent,within,cleanup} from '@testing-library/react'
import {describe,it,expect,vi,afterEach} from 'vitest'
import {STBaoxinHoldingBridge} from './STBaoxinHoldingBridge'
import type {BaoxinHoldingBridge} from './STBaoxinHoldingBridge'
import fixture from './__fixtures__/baoxin-holding-bridge.json'
const data=fixture as BaoxinHoldingBridge
afterEach(cleanup)

describe('Baoxin later source update',()=>{
 it('explains the whole selected bridge without full-period completion claims',()=>{
  render(<STBaoxinHoldingBridge data={data} onOtherChains={vi.fn()}/> )
  const table=screen.getByRole('region',{name:'宝馨持股变化桥接表'})
  expect(within(table).getAllByRole('row')).toHaveLength(5)
  expect(screen.getByText(/原先缺解释的2,766万股/)).toBeInTheDocument()
  expect(screen.getByText(/未解释差额0万股/)).toBeInTheDocument()
 })
 it('keeps default, ruling and historical knowledge separate',()=>{
  render(<STBaoxinHoldingBridge data={data} onOtherChains={vi.fn()}/> )
  fireEvent.click(screen.getByText('942万为何只登记了932万？'))
  expect(screen.getByText(/叶铭康（H7302）的10万股/)).toBeVisible()
  fireEvent.click(screen.getByText('以物抵债，已经等于股份过户了吗？'))
  expect(screen.getByText(/尚未过户，其一致行动人身份当时仍保留/)).toBeVisible()
 })
 it('switches full windows and returns to other chains',()=>{
  const back=vi.fn();render(<STBaoxinHoldingBridge data={data} onOtherChains={back}/> )
  fireEvent.click(screen.getByText('这些完成公告后，个股与市场有什么不同？'))
  fireEvent.change(screen.getByLabelText('宝馨补证观察窗口'),{target:{value:'20'}})
  expect(screen.getAllByText(/未满窗口/).length).toBeGreaterThan(0)
  fireEvent.click(screen.getByRole('button',{name:'回看威领、龙元、沐邦的阶段对照 →'}));expect(back).toHaveBeenCalledOnce()
 })
})
