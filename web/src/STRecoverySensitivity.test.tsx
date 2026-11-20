import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STRecoveryPath} from './STRecoveryPath'
import {endpointSensitivity} from './recoveryPathCalculation'
import data from './__fixtures__/market-stage-experience.json'
import expected from './__fixtures__/recovery-sensitivity-expected.json'
afterEach(cleanup)
it('compares common and endpoint-only sets against independent decimal calculations',()=>{
 const windows=endpointSensitivity(data)!;expect(windows).toHaveLength(5)
 for(const [j,s]of windows.entries()){const e=expected.windows[j];expect([s.members,s.positive,s.zero,s.excluded]).toEqual([e.members,e.positive,e.zero,e.missing_or_conflicting]);expect(s.extraSymbols).toEqual(e.extra_symbols);expect(s.median).toBeCloseTo(Number(e.median_pct),10);expect(s.commonMedian).toBeCloseTo(Number(e.common_median_pct),10)}
})
it('keeps a valid endpoint when intermediate stage start is missing, but excludes a missing final endpoint',()=>{
 const changed=structuredClone(data);const r=changed.stages[4].rows.find(r=>r.symbol==='000010')!;r.endpoints[0].status='primary_missing';r.endpoints[0].primary_close=null
 expect(endpointSensitivity(changed)![4].members).toBe(141)
 r.endpoints[1].status='primary_missing';r.endpoints[1].primary_close=null
 expect(endpointSensitivity(changed)).toBeNull() // the declared common sample is now inconsistent
})
it('shows the sensitivity and explains why near zero is not universal recovery',()=>{
 render(<STRecoveryPath data={data}/>);fireEvent.click(screen.getByText('只选完整记录的139家，会改变结论吗？'));const table=screen.getByRole('table',{name:'同一起点，不同完整性要求下的累计涨跌'});expect(table).toHaveTextContent('-0.36%');expect(table).toHaveTextContent('-0.05%');expect(table).toHaveTextContent('-20.74%');expect(screen.getByText(/典型价格接近起点/)).toBeVisible()
})
