import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STEarningsWarning} from './STEarningsWarning'
import raw from './__fixtures__/earnings-warning.json'
import type {RegimeEarningsWarning} from './stRegimeTypes'
afterEach(cleanup)
const data=raw as unknown as RegimeEarningsWarning
it('answers the different warning conditions and compares four financial combinations at a common window',()=>{
 render(<STEarningsWarning data={data}/>);expect(screen.getByRole('heading',{name:'盈利和现金都转好，为什么还在ST？'})).toBeVisible();expect(screen.getByText('-53.79%')).toBeVisible()
 expect(screen.getByRole('rowheader',{name:/ST天际.*盈利 · 现金净流入/})).toBeVisible();expect(screen.getByRole('rowheader',{name:/华鹏.*亏损 · 现金净流入/})).toBeVisible()
 expect(screen.getByText(/天际7月15日才入ST.*不加入原固定150或12只摘帽组/)).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'盈利现金案例价格窗口'}),{target:{value:'5'}});expect(screen.getByText('+10.35%')).toBeVisible();expect(screen.getByText(/2026-10-30 → 2026-11-06/)).toBeVisible()
})
it('retains the original positive forecast and separates actual cash observations',()=>{
 render(<STEarningsWarning data={data}/>);fireEvent.click(screen.getByText('沿时间线看：预告、正式处罚、中报、三季报'))
 expect(screen.getByText(/7月14日.*预告.*2.2亿至2.6亿元.*不能说当时完全没有盈利信息/)).toBeVisible()
 expect(screen.getByText(/8月21日.*经营现金仍为-2,106.64万元/)).toBeVisible();expect(screen.getByText(/第三季单季现金.*26,549.27万元/)).toBeVisible()
})
it('does not turn received or publication dates into an automatic countdown and preserves the regulatory exception',()=>{
 render(<STEarningsWarning data={data}/>);fireEvent.click(screen.getByText('为什么“调查办理终结”也不等于可以立刻撤销？'))
 expect(screen.getByText(/2026-08-07收到.*2026-08-08公开.*不显示自动摘帽倒计时/)).toBeVisible()
 expect(screen.getByText(/后续处罚决定或结案通知显示未触及.*不能把“本案办理终结”/)).toBeVisible()
 const link=screen.getAllByRole('link',{name:/股票上市规则.*第159页/})[0];expect(link.getAttribute('href')).toContain('#page=159')
})
it('keeps original quote channels and financial sources inspectable without duplicate page fragments',()=>{
 render(<STEarningsWarning data={data}/>);fireEvent.click(screen.getByText('核五家公司各自警示、财报原件与报价范围'));expect(screen.getByText(/250个收盘点.*125个实际成交日/)).toBeVisible()
 expect(screen.getByText(/两份响应来自同一腾讯核对渠道/)).toBeVisible();fireEvent.click(screen.getByText('*ST华鹏：条件与来源'))
 const links=screen.getAllByRole('link',{name:/山东华鹏2026年第三季度报告.*第2页/});expect(links.every(x=>x.getAttribute('href')?.match(/#page=/g)?.length===1)).toBe(true)
})
it('does not create an explanation for a legacy snapshot without evidence',()=>{const {container}=render(<STEarningsWarning data={null}/>);expect(container).toBeEmptyDOMElement()})
