import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {ReadingChart} from './ReadingChart'
import type {ReadingSeries} from './readingTypes'

const dates=['2026-05-29','2026-06-01','2026-06-02']
const series:ReadingSeries[]=[{key:'stock',name:'示例股票',change_pct:-10,points:dates.map((date,i)=>({date,value:100-i*5,level:100-i*5}))}]

describe('uncertain date interval price observation',()=>{
  afterEach(cleanup)
  it('uses reference levels throughout legend, axis, cursor and table without a return claim',()=>{
    const view=render(<ReadingChart label="区间价格观察" series={series} valueMode="index" dateRange={{from:'2026-06-01',through:'2026-06-02'}}/>)
    expect(view.container.querySelector('.reading-chart-legend strong')).toHaveTextContent('90.00')
    expect(view.container.textContent).not.toContain('%')
    expect(screen.getByRole('img')).toHaveAccessibleName(/不以提问日计算收益/)
    fireEvent.change(screen.getByRole('slider'),{target:{value:'0'}})
    expect(view.container.querySelector('.reading-chart-cursor')).toHaveTextContent('2026-05-29示例股票 100.00')
    fireEvent.click(screen.getByText('逐日数值'))
    expect(screen.getByRole('row',{name:'2026-06-01 95.00'})).toBeVisible()
    expect(view.container.querySelector('.reading-review-boundary')).not.toBeInTheDocument()
  })
  it('places a weekend-only interval between observed sessions without inventing weekend points',()=>{
    const view=render(<ReadingChart label="周末区间" series={series} valueMode="index" dateRange={{from:'2026-05-30',through:'2026-05-31'}}/>)
    const group=screen.getByRole('group',{name:'可能提问区间：2026-05-30至2026-05-31'})
    const band=group.querySelector('rect')!
    expect(Number(band.getAttribute('x'))).toBeGreaterThan(54)
    expect(Number(band.getAttribute('x'))+Number(band.getAttribute('width'))).toBeLessThan(487)
    fireEvent.click(screen.getByText('逐日数值'))
    expect(screen.getAllByRole('row')).toHaveLength(4)
    expect(view.container.querySelector('.reading-question-marker')).not.toBeInTheDocument()
  })
  it.each([
    {from:'2026-05-28',through:'2026-05-30'},
    {from:'2026-06-01',through:'2026-06-05'},
  ])('clips a partially visible interval to the plot: %j',dateRange=>{
    render(<ReadingChart label="裁切区间" series={series} valueMode="index" dateRange={dateRange}/>)
    const band=screen.getByRole('group',{name:/可能提问区间/}).querySelector('rect')!
    const x=Number(band.getAttribute('x')),width=Number(band.getAttribute('width'))
    expect(x).toBeGreaterThanOrEqual(54);expect(width).toBeGreaterThanOrEqual(2)
    expect(x+width).toBeLessThanOrEqual(920)
  })
  it.each([
    {from:'2026-05-20',through:'2026-05-21'},
    {from:'2026-06-03',through:'2026-06-04'},
    {from:'2026-06-02',through:'2026-06-01'},
    {from:'unknown',through:'2026-06-02'},
  ])('does not draw an unsupported or disjoint interval: %j',dateRange=>{
    render(<ReadingChart label="无有效交集" series={series} valueMode="index" dateRange={dateRange}/>)
    expect(screen.queryByRole('group',{name:/可能提问区间/})).not.toBeInTheDocument()
  })
  it('retains missing prices as gaps and missing index values rather than zero',()=>{
    const view=render(<ReadingChart label="有缺口的区间" valueMode="index" series={[{...series[0],points:series[0].points.map((p,i)=>({...p,level:i===1?null:p.level}))}]}/>)
    const line=view.container.querySelector('.reading-line')!.getAttribute('d')!
    expect(line.match(/M/g)).toHaveLength(2);expect(line).not.toContain('NaN')
    fireEvent.change(screen.getByRole('slider'),{target:{value:'1'}})
    expect(view.container.querySelector('.reading-chart-cursor')).toHaveTextContent('示例股票 待更新')
    expect(screen.getByText(/曲线空档表示缺少可用报价/)).toBeVisible()
  })
  it('does not silently normalize an impossible date into a different day',()=>{
    const points=['2026-02-27','2026-03-02','2026-03-03'].map(date=>({date,value:100,level:100}))
    render(<ReadingChart label="不可能的日期" series={[{...series[0],points}]} valueMode="index" dateRange={{from:'2026-02-30',through:'2026-03-01'}}/>)
    expect(screen.queryByRole('group',{name:/可能提问区间/})).not.toBeInTheDocument()
  })
})
