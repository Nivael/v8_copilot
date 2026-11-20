import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {RiskListNov20} from './RiskListNov20'
afterEach(cleanup)
it('keeps dated SZSE proof separate from an undated SSE table and empty delisting table',()=>{
 render(<RiskListNov20 priceAsOf="2026-11-20"/>);fireEvent.click(screen.getByText('11月20日的官方ST名单，已核到哪一步？'))
 const t=screen.getByRole('table');expect(t).toHaveTextContent('74只');expect(t).toHaveTextContent('68只')
 expect(t).toHaveTextContent('2026-11-20');expect(t).toHaveTextContent('2026-11-21')
 expect(t).toHaveTextContent('未声明，20日仍待确认');expect(t).toHaveTextContent('未声明，不认证20日为零')
 expect(screen.getByText(/两份列表恰好相同/)).toBeVisible()
 fireEvent.click(screen.getByText('分页、分类及来源怎样核？'))
 expect(screen.getByText(/39只创业板A股/)).toBeVisible()
 expect(screen.getByRole('link',{name:'深市风险警示表第一页 ↗'})).toHaveAttribute('href',expect.stringContaining('CATALOGID=fxjsb'))
})
it('does not present the target-day roster as a later or earlier market snapshot',()=>{
 render(<RiskListNov20 priceAsOf="2026-11-19"/>);expect(screen.queryByRole('table')).not.toBeInTheDocument()
 expect(screen.queryByText('11月20日的官方ST名单，已核到哪一步？')).not.toBeInTheDocument()
})
