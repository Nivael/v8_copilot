import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STCashMarketComparison,cashMarketBound} from './STCashMarketComparison'
import fixture from './__fixtures__/cash-market-comparison.json'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
it('compares identical market-day lengths with matched benchmarks and preserves the suspended endpoint',()=>{
 render(<STCashMarketComparison data={fixture as unknown as STRegimeData}/>)
 const table=screen.getByRole('table',{name:'各事项公告日收盘后5个市场交易日的表现'})
 const rows=within(table).getAllByRole('row')
 expect(rows[1]).toHaveTextContent('2026-08-21 → 2026-08-28')
 expect(rows[1]).toHaveTextContent('缺成交端点')
 expect(rows[2]).toHaveTextContent('-14.64%+1.02%+0.65%')
 expect(rows[3]).toHaveTextContent('-2.54%-4.35%-3.36%')
 expect(screen.getByText(/下一交易日上涨/)).toHaveTextContent('20个市场交易日后为-24.07%')
 expect(screen.getByText(/8月25日另有摘帽申请/)).toHaveTextContent('不能倒填为当时已知')
 expect(screen.getByText(/旧研究资料截至/)).toHaveTextContent('2026-11-06')
 fireEvent.click(screen.getByRole('button',{name:'公告日收盘后1个市场交易日'}))
 expect(screen.getByRole('button',{name:'公告日收盘后1个市场交易日'})).toHaveAttribute('aria-pressed','true')
 const short=screen.getByRole('table',{name:'各事项公告日收盘后1个市场交易日的表现'})
 expect(within(short).getAllByRole('row')[1]).toHaveTextContent('+2.48%-0.94%-1.42%')
 expect(screen.getByText(/两件京蓝事项的下一交易日都上涨/)).toHaveTextContent('不是两次独立实验')
})
it.each(['price','date','missing','warning','cutoff'])('stops old interpretation when the bound evidence changes: %s',kind=>{
 const d=structuredClone(fixture)
 if(kind==='price')d.themes.removal_followup.new_event_windows[0].windows['5'].stock_pct=0
 if(kind==='date')d.themes.shenwu_execution.observations[0].published_on='2026-10-14'
 if(kind==='missing')d.themes.removal_followup.new_event_windows=[]
 if(kind==='warning')d.themes.removal_followup.warning.effective_on='2026-09-01'
 if(kind==='cutoff')d.through='2026-11-19'
 expect(cashMarketBound(d as unknown as STRegimeData)).toBe(false)
 render(<STCashMarketComparison data={d as unknown as STRegimeData}/>)
 expect(screen.getByRole('status')).toHaveTextContent('暂不显示旧窗口结论')
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
