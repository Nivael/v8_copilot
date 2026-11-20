import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {cumulativeMarketContext} from './recoveryPathCalculation'
import {STCumulativeMarketContext} from './STCumulativeMarketContext'
import data from './__fixtures__/market-stage-experience.json'
import expected from './__fixtures__/cumulative-market-expected.json'
afterEach(cleanup)
it('matches independent decimal compounding and direct market endpoints',()=>{
 const rows=cumulativeMarketContext(data)!;expect(rows).toHaveLength(5)
 rows.forEach((r,j)=>{const e=expected.rows[j];expect(r.marketPct).toBeCloseTo(Number(e.market_cumulative_pct),10);expect(r.stPct).toBeCloseTo(Number(e.dynamic_st_cumulative_pct),10);expect(r.fixedMedian).toBeCloseTo(Number(e.fixed_common_median_pct),10);expect(r.relativePP).toBeCloseTo(Number(e.fixed_median_minus_market_pp),10);expect(r.outperform).toBe(e.common_outperform_market)})
})
it('rejects invalid reference returns rather than silently converting them to zero',()=>{
 const invalid=structuredClone(data);invalid.stages[1].market_pct='not a price return';expect(cumulativeMarketContext(invalid)).toBeNull();invalid.stages[1].market_pct='-100';expect(cumulativeMarketContext(invalid)).toBeNull()
})
it('distinguishes absolute losses, relative performance and three different objects',()=>{
 render(<STCumulativeMarketContext data={data}/>);expect(screen.getByText(/中位数相对大盘多3.07个百分点/)).toBeVisible();const table=screen.getByRole('table',{name:'统一从7月3日收盘起算，累计变化（%）'});expect(table).toHaveTextContent('-23.84%');expect(table).toHaveTextContent('-19.88%');expect(table).toHaveTextContent('-20.77%');expect(table).toHaveTextContent('76／139');expect(screen.getByText(/不要求个股上涨/)).toBeVisible()
})
