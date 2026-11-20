import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STRecoveryPath} from './STRecoveryPath'
import {recoveryPath} from './recoveryPathCalculation'
import data from './__fixtures__/market-stage-experience.json'
import expected from './__fixtures__/recovery-path-expected.json'
afterEach(cleanup)
it('matches independently calculated decimal endpoint paths for all common companies',()=>{
 const p=recoveryPath(data)!;expect(p.members).toBe(139)
 for(const [j,s]of p.summaries.entries()){const e=expected.summaries[j];expect([s.positive,s.zero,s.negative]).toEqual([e.positive,e.zero,e.negative]);expect(s.median).toBeCloseTo(Number(e.median_pct),10)}
 for(const r of p.rows){const e=expected.rows.find(x=>x.symbol===r.symbol)!;r.cumulative.forEach((v,j)=>expect(v).toBeCloseTo(Number(e.cumulative[j]),10))}
 expect([p.julyLosers,p.augustRose,p.recovered,p.augustPositive,p.stillPositive]).toEqual([118,103,51,67,19])
})
it('rejects broken continuity or unverified prices instead of treating gaps as zero',()=>{
 const broken=structuredClone(data);broken.stages[1].rows.find(r=>r.symbol==='000010')!.endpoints[0].primary_close='999';expect(recoveryPath(broken)).toBeNull()
 const missing=structuredClone(data);missing.stages[2].rows.find(r=>r.symbol==='000010')!.endpoints[1].primary_close=null;expect(recoveryPath(missing)).toBeNull()
 const unverified=structuredClone(data);unverified.stages[0].rows.find(r=>r.symbol==='000010')!.status='unverified';expect(recoveryPath(unverified)).toBeNull()
})
it('explains rebound versus recovery before optional individual paths',()=>{
 render(<STRecoveryPath data={data}/>);expect(screen.getByText(/其中103家在8月上涨/)).toBeVisible();const table=screen.getByRole('table',{name:'同一批公司，相对7月3日收盘的累计路径'});expect(table).toHaveTextContent('-20.77%');expect(table).toHaveTextContent('2026-08-31');fireEvent.click(screen.getByText('怎样计算，逐家公司是否一致？'));expect(within(screen.getByRole('table',{name:'139家连续价格路径（%）'})).getAllByRole('row')).toHaveLength(140)
})
