import {cleanup,render,screen,fireEvent} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {MarketBreadthReading} from './MarketBreadthReading'
import type {BreadthReading} from './readingTypes'
afterEach(cleanup)
const a={name:'沪深A股',listed_source_stocks:5224,observed_trading_stocks:5216,nontrading_stocks:8,advancing:297,declining:4897,flat:22,declining_5pct_or_more:2707,median_return_pct:-5.114705,advancing_pct:5.694,declining_5pct_or_more_pct:51.898}
const data:BreadthReading={availability:'available',as_of:'2026-11-20',source_digest:'a'.repeat(64),observed_at:'2026-11-21T00:00:00+08:00',source_file_count:8,scope:'SSE_SZSE_A_shares_not_BSE',groups:[a,{...a,name:'当日ST简称组'}],sources:[],limits:[],transport_note:'Official mixed transports'}
it('shows one purpose at a time and keeps the old daily denominator intact',()=>{
 render(<MarketBreadthReading data={data} priceAsOf="2026-11-20"/>);expect(screen.getByRole('heading',{name:'先分清风险来自哪里'})).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:'当天跌得多广？'}));expect(screen.getByRole('heading',{name:'下跌是否遍及多数股票？'})).toBeVisible()
 expect(screen.queryByRole('heading',{name:'这次下跌，什么时候开始变得普遍？'})).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'这次怎样持续转弱？'}))
 expect(screen.getByRole('heading',{name:'这次下跌，什么时候开始变得普遍？'})).toBeVisible()
 expect(screen.queryByRole('heading',{name:'下跌是否遍及多数股票？'})).not.toBeInTheDocument()
 expect(screen.getByRole('button',{name:'这次怎样持续转弱？'})).toHaveAttribute('aria-pressed','true')
 expect(screen.getByText(/尚未满5日/)).not.toBeVisible()
 fireEvent.click(screen.getByText('展开事后行情与未满窗口'));expect(screen.getByText(/尚未满5日/)).toBeVisible();expect(screen.getByText(/尚未满5日/)).toHaveTextContent('中证全指')
 fireEvent.click(screen.getByRole('button',{name:'当天跌得多广？'}));expect(screen.getByText(/有成交的5216只股票中/)).toBeVisible()
})
it('date inspection uses the selected day and the complete raw series stays expandable',()=>{
 render(<MarketBreadthReading data={data} priceAsOf="2026-11-20"/>);fireEvent.click(screen.getByRole('button',{name:'这次怎样持续转弱？'}))
 fireEvent.change(screen.getByRole('combobox',{name:'近期广度观察日'}),{target:{value:'2026-11-12'}})
 expect(screen.getByText(/2026-11-12：/)).toHaveTextContent('连续计数为1日')
 expect(screen.getByRole('img',{name:/上涨参与面与大跌比例/})).toBeVisible()
 expect(screen.getByRole('table',{name:'沪深同日有成交股票作比例分母，非账户收益'})).not.toBeVisible()
 fireEvent.click(screen.getByText('展开逐日数字'));expect(screen.getByRole('table',{name:'沪深同日有成交股票作比例分母，非账户收益'})).toBeVisible();expect(screen.getByRole('columnheader',{name:'中证全指当日'})).toBeVisible()
})
it('opens the severity comparison directly from the first-screen evidence answer',()=>{
 render(<MarketBreadthReading data={data} priceAsOf="2026-11-20"/>);
 expect(screen.getByRole('complementary',{name:'风险信号怎样读'})).toHaveTextContent('39.5%')
 fireEvent.click(screen.getByRole('button',{name:'核对冲击与三日确认的先后'}));
 expect(screen.getByRole('button',{name:'冲击与持续性怎样分开看？'})).toHaveAttribute('aria-pressed','true')
 expect(screen.getByRole('region',{name:'当日冲击与连续确认'})).toBeVisible()
 expect(screen.getByRole('table',{name:'全部符合示例的日期，包含尚未三日确认的情况'})).toBeVisible()
 expect(screen.queryByRole('heading',{name:'先分清风险来自哪里'})).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'先看风险线索'}));
 expect(screen.getByRole('heading',{name:'先分清风险来自哪里'})).toBeVisible()
})
