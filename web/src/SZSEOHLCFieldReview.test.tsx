import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {SZSEOHLCFieldReview} from './SZSEOHLCFieldReview'
afterEach(cleanup)
it('does not call an upward single-price day or zero-volume reference rows limit-down',()=>{
 render(<SZSEOHLCFieldReview priceAsOf="2026-11-20"/>);fireEvent.click(screen.getByText('20日深市，同价K线一定是跌停吗？'))
 expect(screen.getByText(/72只有成交，2只无成交/)).toBeVisible()
 const coverage=screen.getByRole('complementary',{name:'深市20日实际限价覆盖'});expect(coverage).toHaveTextContent('已核71只');expect(coverage).toHaveTextContent('美丽（000010.SZ）请求连接中断');expect(coverage).toHaveTextContent('不能把部分覆盖的零写成完整72只零跌停')
 const t=screen.getByRole('table');expect(t).toHaveTextContent('*ST发展 · 000838.SZ：1.32元，参考前收1.20元')
 expect(t).toHaveTextContent('ST汇洲 · 002122.SZ');expect(t).toHaveTextContent('*ST岭南 · 002717.SZ')
 expect(screen.getByText(/这份原始报表有12列/)).toHaveTextContent('没有实际涨跌停价字段')
 fireEvent.click(screen.getByText('原始列、收低记录与来源'))
 expect(screen.getByText(/原表列：/)).toHaveTextContent('开盘、最高、最低、今收')
 expect(screen.getByRole('link',{name:'深交所20日原始行情导出 ↗'})).toHaveAttribute('href',expect.stringContaining('2026-11-20'))
})
it('does not relabel an observation to another day',()=>{
 render(<SZSEOHLCFieldReview priceAsOf="2026-11-19"/>);expect(screen.queryByText('20日深市，同价K线一定是跌停吗？')).not.toBeInTheDocument()
})
