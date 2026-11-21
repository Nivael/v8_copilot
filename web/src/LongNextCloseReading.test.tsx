import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {LongNextCloseReading} from './LongNextCloseReading'
import split from './longNextCloseReading.json'
const original=split.alignment_sha256
afterEach(()=>{cleanup();split.alignment_sha256=original})
it('retains all six fixed-endpoint paths and does not claim an executable next-close sale',()=>{
 render(<LongNextCloseReading/>);
 fireEvent.click(screen.getByText('等到下一交易日收盘，原后窗还剩多少变化？'))
 const r=screen.getByRole('region',{name:'下一收盘与剩余后窗'})
 expect(within(within(r).getByRole('table',{name:'全部六次提示：前一段与剩余段需要复合，不能直接相加'})).getAllByRole('row')).toHaveLength(7)
 expect(r).toHaveTextContent('大盘首日涨3.46%，余4日跌0.44%')
 expect(r).toHaveTextContent('ST首日跌1.86%，余4日涨4.03%')
 expect(r).toHaveTextContent('未满5日，仅拆成1＋2日')
 expect(r).toHaveTextContent('不能单独称为隔夜跳空')
 expect(r).toHaveTextContent('不是假定能够在该价卖出')
 expect(r).toHaveTextContent('也未校准误报率')
 expect(within(r).getByRole('link',{name:'查看拆分核验与原研究记录 →'})).toHaveAttribute('href','/runs#research-'+split.research_run_id)
})
it('withholds the split when the original alignment changes',()=>{
 split.alignment_sha256='changed';render(<LongNextCloseReading/>);
 expect(screen.getByRole('status')).toHaveTextContent('暂不合并')
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
