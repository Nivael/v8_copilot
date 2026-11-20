import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {MarketRiskQuestions} from './MarketRiskQuestions'
import type {BreadthReading} from './readingTypes'
import recent from './recentMarketBreadth.json'
const last=recent.rows[recent.rows.length-1]
const data={as_of:recent.as_of,groups:[{observed_trading_stocks:last.trading,advancing:last.advancing,declining_5pct_or_more:last.declining_5pct_or_more}]} as BreadthReading
afterEach(cleanup)
it('keeps persistence, severity, relative weakness and execution evidence separate',()=>{
 const open=vi.fn();render(<MarketRiskQuestions data={data} onRead={open}/>);
 expect(screen.getByRole('table')).toHaveTextContent('连续7个交易日')
 expect(screen.getByRole('table')).toHaveTextContent('51.9%')
 expect(screen.getByRole('table')).toHaveTextContent('未满5日')
 expect(screen.getByText(/后者不是跌停率/)).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:'看转弱过程'}));expect(open).toHaveBeenCalledWith('recent')
 fireEvent.click(screen.getByRole('button',{name:'看当天分布'}));expect(open).toHaveBeenLastCalledWith('today')
 fireEvent.click(screen.getByRole('button',{name:'看ST同窗对照'}));expect(open).toHaveBeenLastCalledWith('st')
 fireEvent.click(screen.getByRole('button',{name:'核对限价与退出缺口'}));expect(open).toHaveBeenLastCalledWith('st')
})
it('does not merge changed dates or denominators with the frozen sequence',()=>{
 const {rerender}=render(<MarketRiskQuestions data={{...data,as_of:'2026-11-23'}} onRead={()=>{}}/>);expect(screen.queryByRole('table')).not.toBeInTheDocument()
 rerender(<MarketRiskQuestions data={{...data,groups:[{...data.groups[0],observed_trading_stocks:1}]}} onRead={()=>{}}/>);expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('shows waiting cost and rebound counterexample before the indicator table',()=>{
 render(<MarketRiskQuestions data={data} onRead={()=>{}}/>)
 const warning=screen.getByRole('complementary',{name:'风险信号怎样读'})
 expect(warning).toHaveTextContent('2026-11-16')
 expect(warning).toHaveTextContent('-5.59%')
 expect(warning).toHaveTextContent('-4.76%')
 expect(warning).toHaveTextContent('反弹反例')
 expect(warning).toHaveTextContent('+1.61%')
 expect(warning).toHaveTextContent('不是你的账户损失')
 expect(warning.compareDocumentPosition(screen.getByRole('table')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})
