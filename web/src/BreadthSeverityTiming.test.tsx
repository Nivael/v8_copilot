import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {BreadthSeverityTiming} from './BreadthSeverityTiming'
import data from './breadthSeverityReading.json'
const original=data.breadth_sha256
afterEach(()=>{cleanup();data.breadth_sha256=original})
it('retains all severity dates and separates prior confirmation from the same-day observation',()=>{
 render(<BreadthSeverityTiming/>);fireEvent.click(screen.getByText('没有三日确认，也可能已经出现大跌扩散吗？'))
 const r=screen.getByRole('region',{name:'当日冲击与连续确认'})
 expect(within(r).getAllByRole('row')).toHaveLength(7)
 expect(r).toHaveTextContent('39.5%')
 expect(r).toHaveTextContent('6天中：1天在前一收盘')
 expect(r).toHaveTextContent('4天当天连续计数仍未达三日')
 expect(r).toHaveTextContent('不是预警命中率')
 expect(r).toHaveTextContent('也不表示此前从未出现其他提示')
 expect(r).toHaveTextContent('并非实际跌停')
 expect(r).toHaveTextContent('当天完整广度在收盘后才确定')
 fireEvent.change(screen.getByRole('combobox',{name:'大跌占比示例分界'}),{target:{value:'10'}})
 expect(within(r).getAllByRole('row')).toHaveLength(25)
 fireEvent.change(screen.getByRole('combobox',{name:'大跌占比示例分界'}),{target:{value:'30'}})
 expect(within(r).getAllByRole('row')).toHaveLength(5)
})
it('withholds the comparison on another breadth source',()=>{
 data.breadth_sha256='changed';render(<BreadthSeverityTiming/>);
 expect(screen.getByRole('status')).toHaveTextContent('暂不合并')
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
it('does not merge the historical comparison into another current date',()=>{
 render(<BreadthSeverityTiming expanded asOf="2026-11-23"/>);
 expect(screen.getByRole('status')).toHaveTextContent('暂不合并')
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
