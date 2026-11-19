import {render,screen,fireEvent,within,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STEndpointReasons} from './STEndpointReasons'
import type {EndpointReasons} from './STEndpointReasons'
import fixture from './__fixtures__/endpoint-reasons.json'
afterEach(cleanup)
const data=fixture as EndpointReasons
it('explains why the two windows have different usable subsets of the same 150 stocks',()=>{
 render(<STEndpointReasons data={data}/>);expect(screen.getByText(/完整93日有146只可比、4只缺口/)).toBeTruthy();expect(screen.getByText(/不是原始成交价/)).toBeTruthy()
 const table=screen.getByRole('table');expect(within(table).getAllByRole('row')).toHaveLength(5);expect(table).toHaveTextContent('7月10日才复牌')
 fireEvent.change(screen.getByLabelText('想核哪段比较？'),{target:{value:'recent'}});expect(table).toHaveTextContent('2026-11-06收盘');expect(within(table).getAllByText('不计算')).toHaveLength(3)
})
it('keeps reference prices out of actual endpoint cells and retains the halt-stage limit',()=>{
 render(<STEndpointReasons data={data}/>);fireEvent.change(screen.getByLabelText('想核哪段比较？'),{target:{value:'recent'}});fireEvent.click(screen.getByRole('button',{name:'*ST岭南'}));fireEvent.click(screen.getByText('查看此公司的原件与价格缺口'));expect(screen.getByText(/有0.45元前复权参考值，但没有实际成交/)).toBeTruthy();expect(screen.getByText(/不把程序期限或目录没检出/)).toBeTruthy()
})
it('distinguishes cash-option settlement, delisting and individualized realized outcomes',()=>{
 render(<STEndpointReasons data={data}/>);expect(screen.getByText(/不能据此推算每个持有人收益/)).toBeTruthy();fireEvent.click(screen.getByText('查看此公司的原件与价格缺口'));expect(screen.getByRole('link',{name:/现金选择权申报结果/}).getAttribute('href')).toContain('2a1b8b3d-7b41-40e1-92d3-c5ab65945d6f.PDF#page=2')
})
it('labels reused sources and non-detection honestly instead of claiming more primary data',()=>{
 render(<STEndpointReasons data={data}/>);fireEvent.click(screen.getByText('本轮复用了什么，哪些没有新增？'));expect(screen.getByText(/新增原件下载0份、新增行情0点/)).toBeTruthy();expect(screen.getByText(/标题未检出不证明不存在目录外/)).toBeTruthy()
})
it('does not add a surface for a legacy snapshot',()=>{const {container}=render(<STEndpointReasons/>);expect(container.firstChild).toBeNull()})
