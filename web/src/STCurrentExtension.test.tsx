import {render,screen,fireEvent,cleanup,within} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import STCurrentExtension from './STCurrentExtension'
import type {CurrentExtension} from './STCurrentExtension'
import fixture from './__fixtures__/current-extension.json'
afterEach(cleanup)
const show=()=>render(<STCurrentExtension data={fixture as CurrentExtension}/> )
it('missing extension preserves the historical page',()=>{const {container}=render(<STCurrentExtension/>);expect(container).toBeEmptyDOMElement()})
it('distinguishes recent weakness from full-period relative resilience',()=>{show();expect(screen.getByRole('heading',{name:'最近9日，ST比大盘跌得更深'})).toBeVisible();expect(screen.getByText(/只有14只上涨/)).toHaveTextContent('147');fireEvent.click(screen.getByText('比较最近9日与7月以来全段'));const table=screen.getByRole('table',{name:'新旧窗口的相对表现'});expect(table).toHaveTextContent('-10.05%');expect(table).toHaveTextContent('-4.65%');expect(table).toHaveTextContent('93日');expect(table).toHaveTextContent('-19.88%')})
it('continues tracking a removed STAR stock without putting it in main-board reference',()=>{show();fireEvent.change(screen.getByRole('combobox'),{target:{value:'688053.SH'}});expect(screen.getByRole('heading',{name:'11月11日摘帽，继续跟踪'})).toBeVisible();expect(screen.getByText(/科创板涨跌幅仍20%/)).toBeVisible();expect(screen.getByRole('table',{name:'重点公司近期同窗表现'})).toHaveTextContent('持续跟踪 · 科创板 · 已离开ST')})
it('keeps proposed donation separate from profit and cash receipt',()=>{show();fireEvent.change(screen.getByRole('combobox'),{target:{value:'002667.SZ'}});expect(screen.getByText(/资本公积/)).toBeVisible();expect(screen.getAllByText(/5亿/).length).toBeGreaterThan(0)})
it('preserves fixed-sample missing endpoints and allows all 150 rows',()=>{show();fireEvent.click(screen.getByText('固定150只：查看缺价、退出与完整样本'));const table=screen.getByRole('table',{name:'最新固定样本价格覆盖'});expect(within(table).getAllByRole('row')).toHaveLength(4);expect(table).toHaveTextContent('002731');fireEvent.click(screen.getByRole('button',{name:'展开全部150只'}));expect(within(table).getAllByRole('row')).toHaveLength(151)})
it('keeps Baoxin publication-order conflict and page-specific evidence',()=>{show();fireEvent.change(screen.getByRole('combobox'),{target:{value:'002514.SZ'}});expect(screen.getByText(/本件仍称南京宇宏/)).toBeVisible();fireEvent.click(screen.getAllByText('依据与下一步核对')[1]);expect(screen.getByText(/11月7日件与11月11日件/)).toBeVisible();expect(screen.getAllByRole('link').some(a=>a.getAttribute('href')?.endsWith('1225666030.PDF#page=4'))).toBe(true)})
