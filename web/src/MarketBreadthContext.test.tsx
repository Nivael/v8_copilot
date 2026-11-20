import {cleanup,render,screen,fireEvent} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import type {BreadthReading} from './readingTypes'
import {MarketBreadthContext} from './MarketBreadthContext'
afterEach(cleanup)
const group={name:'沪深A股',listed_source_stocks:10,observed_trading_stocks:8,nontrading_stocks:2,advancing:1,declining:6,flat:1,declining_5pct_or_more:4,median_return_pct:-5,advancing_pct:12.5,declining_5pct_or_more_pct:50}
const data:BreadthReading={availability:'available',as_of:'2026-11-20',source_digest:'a'.repeat(64),observed_at:'2026-11-21T00:00:00+08:00',source_file_count:8,scope:'SSE_SZSE_A_shares_not_BSE',groups:[group,{...group,name:'当日ST简称组'}],sources:[{label:'上交所股票行情',url:'https://www.sse.com.cn/market/price/report/'}],limits:['单日截面不能说明连续恶化。'],transport_note:'首控制页为HTTPS；末页和Excel为官方HTTP。'}
it('shows actual trading denominators and keeps source limits expandable',()=>{
 render(<MarketBreadthContext data={data} priceAsOf="2026-11-20"/>);expect(screen.getAllByRole('row')).toHaveLength(3)
 expect(screen.getByText(/“跌幅至少5%”是固定幅度统计/)).toBeVisible()
 expect(screen.queryByRole('status')).not.toBeInTheDocument()
 expect(screen.getByText('单日截面不能说明连续恶化。')).not.toBeVisible()
 fireEvent.click(screen.getByText('范围、原件与仍缺什么'));expect(screen.getByText('单日截面不能说明连续恶化。')).toBeVisible()
 expect(screen.getByRole('link',{name:'上交所股票行情 ↗'})).toHaveAttribute('href',data.sources[0].url)
})
it('calls out mismatched dates and withholds a wrong universe',()=>{
 const view=render(<MarketBreadthContext data={data} priceAsOf="2026-11-19"/>);expect(screen.getByRole('status')).toHaveTextContent('不能合成同日结论')
 view.rerender(<MarketBreadthContext data={{...data,groups:[group]}} priceAsOf="2026-11-20"/>);expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
