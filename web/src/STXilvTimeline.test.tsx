import {cleanup,render,screen,fireEvent,within} from '@testing-library/react'
import {afterEach,describe,it,expect} from 'vitest'
import {STXilvTimeline} from './STXilvTimeline'
import type {XilvTimeline} from './STXilvTimeline'
import fixture from './__fixtures__/xilv-timeline.json'
afterEach(cleanup)
const data=fixture as XilvTimeline
describe('Xilv process reading',()=>{
 it('leads with the path and shared calendar windows, then changes the month explanation',()=>{
  render(<STXilvTimeline data={data}/>);expect(screen.getByRole('heading',{name:'先跌、修复、冲高、回撤、再反弹'})).toBeTruthy()
  expect(screen.getByRole('img',{name:/7月3日收盘为零/})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'07/31—08/31'}));expect(screen.getByText(/西旅、ST、大盘与小盘都回升/)).toBeTruthy()
  expect(screen.getByText(/最高收盘和首次恢复日期来自事后/)).toBeTruthy()
 })
 it('distinguishes signature, deposit and implementation while keeping the negative reaction',()=>{
  render(<STXilvTimeline data={data}/>);fireEvent.change(screen.getByLabelText('选择一个进展或反例'),{target:{value:'agreement'}})
  expect(screen.getByText(/5000万元是监督方指定账户/)).toBeTruthy();expect(screen.getByText('-9.98%')).toBeTruthy()
  fireEvent.click(screen.getByText('展开本事项原件、披露日与署期'));const link=screen.getByRole('link',{name:/关于与重整投资人签署/});expect(link.getAttribute('href')).toContain('1225575791.PDF')
 })
 it('keeps weekend disclosure anchors and incomplete windows, including both sides of amendment',()=>{
  render(<STXilvTimeline data={data}/>);fireEvent.change(screen.getByLabelText('选择一个进展或反例'),{target:{value:'loan'}})
  expect(screen.getByText(/收到首期1000万元/)).toBeTruthy();expect(screen.getByText(/披露前一交易日 2026-10-30/)).toBeTruthy()
  expect(screen.getAllByText('未满窗口').length).toBe(3);expect(screen.getByText('截至2026-11-19仅14日')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('选择一个进展或反例'),{target:{value:'amendment'}});expect(screen.getByText(/同时删去牵头人/)).toBeTruthy()
 })
 it('retains selection, causal and source-date limits without another fetch or added stock',()=>{
  const {container}=render(<STXilvTimeline data={data}/>);expect(screen.getByText(/11月5日尚未收到受理文书/)).toBeTruthy()
  expect(screen.getByText(/诉讼、担保与其他股东借款/)).toBeTruthy();expect(within(container).getAllByRole('table').length).toBe(2)
 })
 it('renders nothing for an old snapshot',()=>{const {container}=render(<STXilvTimeline/>);expect(container.firstChild).toBeNull()})
})
