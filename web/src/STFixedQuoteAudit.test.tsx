import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STFixedQuoteAudit} from './STFixedQuoteAudit'
import type {RegimeFixedQuoteAudit} from './stRegimeTypes'
import raw from './__fixtures__/fixed-quote-audit.json'
const data=raw as RegimeFixedQuoteAudit
afterEach(cleanup)
describe('固定样本核价覆盖',()=>{
 it('答案先区分148只原价与11只前复权差异，默认只列差异者',()=>{
  render(<STFixedQuoteAudit data={data}/>);expect(screen.getByRole('heading',{name:'固定150只的行情，核对到了哪一步？'})).toBeVisible();expect(screen.getByText(data.answer)).toBeVisible();expect(screen.getAllByText('35/146')).toHaveLength(2);expect(screen.getAllByText('-12.20%')).toHaveLength(2);expect(screen.getByText(/37,166/)).toBeVisible();expect(screen.getByText('603517')).toBeVisible();expect(screen.queryByText('603398')).not.toBeInTheDocument()
 })
 it('同窗切换保留两种口径与不配对数，不把原始价一致当复权一致',()=>{
  render(<STFixedQuoteAudit data={data}/>);fireEvent.change(screen.getByLabelText('固定样本核价窗口'),{target:{value:'20'}});expect(screen.getAllByText('15/146')).toHaveLength(2);expect(screen.getByText(/0.2000个百分点/)).toBeVisible();fireEvent.change(screen.getByLabelText('固定样本核价窗口'),{target:{value:'5'}});expect(screen.getAllByText('117/147')).toHaveLength(2)
 })
 it('150全列可查个股，退出记录与缺端点不填零',()=>{
  render(<STFixedQuoteAudit data={data}/>);fireEvent.change(screen.getByLabelText('固定样本核价范围'),{target:{value:'all'}});fireEvent.change(screen.getByLabelText('核价查找公司'),{target:{value:'600491'}});expect(screen.getByText(/^600491/)).toBeVisible();expect(screen.getAllByText('无共同成交端点')).toHaveLength(2);fireEvent.change(screen.getByLabelText('核价查找公司'),{target:{value:''}});fireEvent.change(screen.getByLabelText('固定样本核价范围'),{target:{value:'prior'}});expect(screen.getByText(/^000016/)).toBeVisible();expect(screen.getByText(/^002731/)).toBeVisible();expect(screen.getAllByRole('cell',{name:'本轮未重放'})).toHaveLength(2);expect(screen.queryByText(/^600491/)).not.toBeInTheDocument()
 })
 it('按需展开可看冻结请求与逐日差异，空搜索不伪造结果',()=>{
  render(<STFixedQuoteAudit data={data}/>);fireEvent.change(screen.getByLabelText('核价查找公司'),{target:{value:'603517'}});fireEvent.click(screen.getByText('核来源与日期'));expect(screen.getAllByRole('link',{name:'冻结报价对应请求 ↗'})).toHaveLength(2);fireEvent.click(screen.getByText('逐日差异原数'));expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(100);fireEvent.change(screen.getByLabelText('核价查找公司'),{target:{value:'不存在'}});expect(screen.getByText('没有符合筛选的公司。')).toBeVisible()
 })
 it('规则前后用同一批公司，细小中位数差异仍保留',()=>{render(<STFixedQuoteAudit data={data}/>);fireEvent.change(screen.getByLabelText('固定样本核价窗口'),{target:{value:'before20'}});expect(screen.getAllByText('34/146')).toHaveLength(2);fireEvent.change(screen.getByLabelText('固定样本核价窗口'),{target:{value:'after20'}});expect(screen.getAllByText('22/146')).toHaveLength(2);expect(screen.getByText('-7.88%')).toBeVisible();expect(screen.getByText('-7.92%')).toBeVisible();expect(screen.getByText(/切换前后窗口不更换公司/)).toBeVisible()})
 it('旧快照不虚构覆盖',()=>{const v=render(<STFixedQuoteAudit data={null}/>);expect(v.container).toBeEmptyDOMElement()})
})
