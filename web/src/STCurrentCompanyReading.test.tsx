import {render,screen,cleanup,fireEvent} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STCurrentCompanyReading} from './STCurrentCompanyReading'
import type {CurrentExtension} from './STCurrentExtension'
import raw from './__fixtures__/current-extension.json'
const data=raw as CurrentExtension
afterEach(cleanup)
it('places current common-window prices alongside new stages and original page evidence',()=>{
 render(<STCurrentCompanyReading data={data} symbol="603398.SH" historicalThrough="2026-11-06"/>)
 expect(screen.getByText(/收盘4.39元/)).toHaveTextContent('个股-31.41%，同期主板ST参考-10.05%，中证全指-4.65%')
 expect(screen.getByText(/不等于法院受理/)).toBeVisible()
 expect(screen.getByText(/接下来核对/)).toBeVisible()
 fireEvent.click(screen.getByText('查看这项更新的原件'))
 expect(screen.getByRole('link',{name:/第2页/})).toHaveAttribute('href',expect.stringContaining('1225669757.PDF#page=2'))
 expect(screen.getByText(/下方截至2026-11-06/)).toBeVisible()
})
it('keeps removed STAR company followed without making it a main-board constituent',()=>{
 render(<STCurrentCompanyReading data={data} symbol="688053.SH" historicalThrough="2026-11-06"/>)
 expect(screen.getByRole('heading',{name:'思科瑞：新进展推进到哪一步？'})).toBeVisible()
 expect(screen.getByText(/不计入主板ST参考/)).toHaveTextContent('已经离开ST名单')
 expect(screen.getByText(/科创板涨跌幅仍20%/)).toBeVisible()
})
it.each(['2026-11-19','2026-11-20'])('never overlays an older update on a newer historical quote %s',historicalThrough=>{
 const {container}=render(<STCurrentCompanyReading data={data} symbol="603398.SH" historicalThrough={historicalThrough}/>)
 expect(container).toBeEmptyDOMElement()
})
it('does not substitute another company when the selected identity is absent',()=>{
 const {container}=render(<STCurrentCompanyReading data={data} symbol="002207.SZ" historicalThrough="2026-11-06"/>)
 expect(container).toBeEmptyDOMElement()
})
it('keeps a missing historical cutoff unknown while showing independently dated new evidence',()=>{
 render(<STCurrentCompanyReading data={data} symbol="603398.SH"/>)
 expect(screen.getByText(/价格截止尚未核得/)).toBeVisible()
 expect(screen.getByText(/收盘4.39元/)).toHaveTextContent('2026-11-19')
})
