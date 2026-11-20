import {cleanup,render,screen} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import type {PriceContext} from './readingTypes'
import {MarketPriceContext} from './MarketPriceContext'
afterEach(cleanup)
const data:PriceContext={as_of:'2026-11-20',start:'2026-08-20',close_observations:61,scope:'price_only_not_crisis_score',source_digest:'a'.repeat(64),rows:['000985.CSI','000300.SH','932000.CSI'].map((code,i)=>({code,name:['中证全指','沪深300','中证2000'][i],twenty_day_change_pct:-9,sixty_day_change_pct:-12,from_window_high_pct:-15,window_high_on:'2026-09-01',above_ma20:false,above_ma60:false,source_url:'https://www.csindex.com.cn/'+code}))}
it('shows three dated price paths and keeps proposed actions behind an expansion',()=>{
 render(<MarketPriceContext data={data} priceAsOf="2026-11-20"/>);expect(screen.getAllByRole('row')).toHaveLength(4)
 expect(screen.getByRole('link',{name:'中证2000 ↗'})).toHaveAttribute('href',data.rows[2].source_url)
 expect(screen.getByText(/不是历史最大回撤/)).toBeVisible()
 expect(screen.getByText(/这些动作尚未完成阈值校准/)).not.toBeVisible()
})
it('withholds mismatched date or missing style index',()=>{
 const view=render(<MarketPriceContext data={data} priceAsOf="2026-11-19"/>);expect(screen.queryByRole('table')).not.toBeInTheDocument()
 view.rerender(<MarketPriceContext data={{...data,rows:data.rows.slice(0,2)}} priceAsOf="2026-11-20"/>);expect(screen.getByRole('status')).toBeVisible()
})
