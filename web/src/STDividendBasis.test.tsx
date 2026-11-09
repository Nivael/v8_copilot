import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STDividendBasis} from './STDividendBasis'
import type {RegimeDividendBasis} from './stRegimeTypes'
import raw from './__fixtures__/dividend-basis.json'
const data=raw as RegimeDividendBasis
afterEach(cleanup)
describe('分派与复权构造解释',()=>{
 it('先解释当日参考与事后回看，不把5.05%当旧边界突破',()=>{
  render(<STDividendBasis data={data}/>);expect(screen.getByRole('heading',{name:'同一天的涨幅，为什么有三种读数？'})).toBeVisible();expect(screen.getByText(/后一个数已包含9月后来分红/)).toBeVisible();expect(screen.getByText(/没有突破这条价格边界/)).toBeVisible();expect(screen.getAllByText('+5.05%').length).toBeGreaterThan(0);expect(screen.getAllByText('+4.99%').length).toBeGreaterThan(0)
 })
 it('三次分派只有两家公司，原窗口与直接差异都保留',()=>{
  render(<STDividendBasis data={data}/>);expect(screen.getByText(data.what_changed)).toBeVisible();expect(screen.getByText('29日')).toBeVisible();expect(screen.getByText('51日')).toBeVisible();expect(screen.getByText(/两家公司三次分派.*不能算三次独立/)).toBeVisible();expect(screen.getAllByText('-2.99%')).toHaveLength(2);expect(screen.getByText('-3.05%')).toBeVisible()
 })
 it('八菱股数与测算总额变化按需看，不推实际到账',()=>{
  render(<STDividendBasis data={data}/>);expect(screen.queryByText(/测算总额从/)).not.toBeVisible();fireEvent.click(screen.getByText('ST八菱：核分红、股数和重建依据'));expect(screen.getByText(/测算总额从28,402,615.7元增至28,408,115.7元，相差5,500元/)).toBeVisible();expect(screen.getAllByText(/没有认证登记日最终股数或实际派付总额/).length).toBeGreaterThan(0);expect(within(screen.getByText('ST八菱：核分红、股数和重建依据').closest('details')!).getByRole('link',{name:/2025\s*年年度权益分派实施公告.*第2页/})).toHaveAttribute('href',data.rows[1].actions[0].date_source.url+'#page=2')
 })
 it('章鼓登记股本不确定性与可转债期保留',()=>{
  render(<STDividendBasis data={data}/>);fireEvent.click(screen.getByText('ST章鼓：核分红、股数和重建依据'));expect(screen.getByText(/可转债转股期.*未独立认证登记日最终股数/)).toBeVisible();expect(screen.getByText(/31,205,297.8元/)).toBeVisible()
 })
 it('来源与前置5月补读范围可展开，不冒充七月目录全量',()=>{
  render(<STDividendBasis data={data}/>);fireEvent.click(screen.getByText('来源、历史判断与未完成范围'));expect(screen.getByText(/新增3份10页原件.*504个报价口径点.*252个成交股票日期/)).toBeVisible();expect(screen.getByText(/不代表已穷尽5月公告/)).toBeVisible()
 })
 it('未通过的重建不沿用成功措辞',()=>{const failed={...data,supported:false,answer:'尚有条件未通过',what_changed:'失败日期保留'};render(<STDividendBasis data={failed}/>);expect(screen.getByText(/重建尚有未通过条件/)).toBeVisible();expect(screen.queryByText(/两家各126个成交日期都能复现/)).not.toBeInTheDocument()})
 it('旧快照不虚构分红解释',()=>{const v=render(<STDividendBasis data={null}/>);expect(v.container).toBeEmptyDOMElement()})
})
