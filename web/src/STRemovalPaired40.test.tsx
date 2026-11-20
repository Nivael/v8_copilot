import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STRemovalPaired40} from './STRemovalPaired40'
import {removalPaired40} from './removalPaired40'
import data from './__fixtures__/removal-mature-windows.json'
import prior from './__fixtures__/removal-era-comparison.json'
import expected from './__fixtures__/removal-paired-40-expected.json'
afterEach(cleanup)
it('pairs the same ten companies and matches independent decimal endpoint checks',()=>{
 const r=removalPaired40(data,prior)!;expect(r.rows).toHaveLength(10);expect(r.waiting).toHaveLength(2);expect(r.median20).toBeCloseTo(Number(expected.summary.median20),10);expect(r.median40).toBeCloseTo(Number(expected.summary.median40),10);expect([r.positive20,r.positive20StillPositive,r.gaveBack,r.extended]).toEqual([5,5,3,2]);
 for(const row of r.rows){const e=expected.rows.find(x=>x.symbol===row.symbol)!;expect(row.return40).toBeCloseTo(Number(e.return40),10);expect(row.next20).toBeCloseTo(Number(e.next20_return),10)}
})
it('never fills an unmatured window or joins a different event date',()=>{
 const changed=structuredClone(data);changed.rows.find(r=>r.symbol==='603838')!.available_market_days=40;const r=removalPaired40(changed,prior)!;expect(r.rows).toHaveLength(10);expect(r.waiting.find(r=>r.symbol==='603838')!.status).toBe('needs_verification');changed.rows[0].anchor='2026-01-01';expect(removalPaired40(changed,prior)).toBeNull()
})
it('explains the denominator and exposes compounded second-leg returns',()=>{
 render(<STRemovalPaired40 data={data} prior={prior}/>);expect(screen.getByText(/3家回吐了部分涨幅/)).toBeVisible();expect(screen.getByText(/11家20日中位数与这里10家40日中位数/)).toBeVisible();fireEvent.click(screen.getByText('核对同一组公司的20日与40日路径'));expect(within(screen.getByRole('table',{name:'同组比较：均从摘帽首日收盘起算'})).getAllByRole('row')).toHaveLength(11);expect(screen.getByText(/四通股份 · 603838：已有22/)).toBeVisible()
})
