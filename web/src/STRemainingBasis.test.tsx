import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STRemainingBasis} from './STRemainingBasis'
import type {RegimeRemainingBasis} from './stRegimeTypes'
import raw from './__fixtures__/remaining-basis.json'
const data=raw as RegimeRemainingBasis
afterEach(cleanup)
describe('剩余构造解释',()=>{
 it('先读重整参考价与旧边界，不将超过5%直接判突破',()=>{render(<STRemainingBasis data={data}/>);expect(screen.getByRole('heading',{name:/这些复权差异/})).toBeVisible();expect(screen.getByRole('heading',{name:/华闻：当日\+5.18%/})).toBeVisible();expect(screen.getByText(/实际收盘等于边界，没有突破/)).toBeVisible();expect(screen.getByText(/新增股份不向原股东分配/)).toBeVisible();expect(screen.getAllByRole('row')).toHaveLength(9)})
 it('京机原件冲突有单独的解释和可展开原式',()=>{render(<STRemainingBasis data={data}/>);fireEvent.change(screen.getByLabelText('剩余差异公司'),{target:{value:'000821'}});expect(screen.getByText(/尚未核到正式更正/)).toBeVisible();expect(screen.getByText(/按印刷分母计算/)).not.toBeVisible();fireEvent.click(screen.getByText('看原页、精度与不符日期'));expect(screen.getByText(/按印刷分母计算.*0.330000.*0.326688/)).toBeVisible();expect(screen.getByText(/是，不能仅凭此产品区分两种输入/)).toBeVisible();expect(screen.getAllByRole('link').every(a=>a.getAttribute('href')?.includes('#page='))).toBe(true)})
 it('智知实派和参考额分开',()=>{render(<STRemainingBasis data={data}/>);fireEvent.change(screen.getByLabelText('剩余差异公司'),{target:{value:'603869'}});expect(screen.getByText(/每股含税现金.025元.*参考额.0237元/)).toBeVisible()})
 it('新增复用与全量限制可展开',()=>{render(<STRemainingBasis data={data}/>);fireEvent.click(screen.getByText('这轮新增、复用与剩余范围'));expect(screen.getByText(/新增9份44页.*复用2份.*共51页/)).toBeVisible();expect(screen.getByText(/两只退出样本原字节重放/)).toBeVisible()})
 it('旧快照不虚构解释',()=>{expect(render(<STRemainingBasis data={null}/>).container).toBeEmptyDOMElement()})
})
