import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STBreadthAlignment} from './STBreadthAlignment'
import {MarketBreadthReading} from './MarketBreadthReading'
import type {BreadthReading} from './readingTypes'
afterEach(cleanup)
const a={name:'沪深A股',listed_source_stocks:5224,observed_trading_stocks:5216,nontrading_stocks:8,advancing:297,declining:4897,flat:22,declining_5pct_or_more:2707,median_return_pct:-5.114705,advancing_pct:5.694,declining_5pct_or_more_pct:51.898}
const data:BreadthReading={availability:'available',as_of:'2026-11-20',source_digest:'a'.repeat(64),observed_at:'2026-11-21T00:00:00+08:00',source_file_count:8,scope:'SSE_SZSE_A_shares_not_BSE',groups:[a,{...a,name:'当日ST简称组'}],sources:[],limits:[],transport_note:'Official mixed transports'}

it('keeps the rebound counterexample and incomplete common window',()=>{
 render(<STBreadthAlignment/>);expect(screen.getByText(/大盘涨1.61%/)).toBeVisible()
 expect(screen.getByText('瑞茂、华幸、东珠：跨渠道核价后，20日有什么不同？')).toBeVisible()
 fireEvent.click(screen.getByText('展开三段事后同窗结果，包括未满窗口'))
 const table=screen.getByRole('table',{name:'从提示日收盘起算；完整5日与未满3日分别标注'});expect(within(table).getAllByRole('row')).toHaveLength(4)
 expect(table).toHaveTextContent('未满5日');expect(table).toHaveTextContent('-5.88%');expect(table).toHaveTextContent('-1.65%')
 expect(screen.getByText(/不能把20日大盘与19日ST拼成同窗/)).toBeVisible()
})
it('exposes the comparison through the existing reading-purpose control',()=>{
 render(<MarketBreadthReading data={data} priceAsOf="2026-11-20"/>);
 fireEvent.click(screen.getByRole('button',{name:'大盘转弱后，ST怎样？'}));expect(screen.getByRole('heading',{name:'大盘修复，ST也会修复吗？'})).toBeVisible()
})
