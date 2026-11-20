import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {STCashDirectionComparison,cashComparisonBound} from './STCashDirectionComparison'
import fixture from './__fixtures__/cash-direction-comparison.json'
import type {STRegimeData} from './stRegimeTypes'
afterEach(cleanup)
it('distinguishes actual issuer receipt, a different claim, shareholder delivery and issuer payment obligation',()=>{
 render(<STCashDirectionComparison data={fixture as unknown as STRegimeData}/>)
 const region=screen.getByRole('region',{name:'现金流向与兑现阶段比较'})
 expect(region).toHaveTextContent('已收齐151,375,161.76元')
 expect(region).toHaveTextContent('37名补偿义务人 → 上市公司（诉请）')
 expect(region).toHaveTextContent('神雾集团所持股份 → 长城资管')
 expect(region).toHaveTextContent('岭南等义务人 → 债券持有人（判项）')
 expect(region).toHaveTextContent('未核实实付不写成零')
 expect(region).toHaveTextContent('尚未检验它能否预测收益')
 expect(screen.getByRole('link',{name:/2025年度公司业绩补偿款支付完毕/})).toBeDefined()
})
it.each(['amount','status','url','date','sha','missing','cutoff'])('withholds comparison on changed evidence: %s',change=>{
 const d=structuredClone(fixture)
 if(change==='amount')d.themes.removal_followup.compensation.total_received_yuan='0'
 if(change==='status')d.themes.shenwu_execution.transfer.status='pending'
 if(change==='url')d.themes.removal_followup.recovery.source.url='https://example.com/wrong'
 if(change==='date')d.themes.removal_followup.recovery.source.published_on='2026-11-20'
 if(change==='sha')d.themes.removal_followup.recovery.source.sha256='wrong'
 if(change==='missing')Reflect.deleteProperty(d.themes,'shenwu_execution')
 if(change==='cutoff')d.through='2026-11-20'
 expect(cashComparisonBound(d as unknown as STRegimeData)).toBe(false)
 render(<STCashDirectionComparison data={d as unknown as STRegimeData}/>)
 expect(screen.getByRole('status')).toHaveTextContent('暂不显示结论')
 expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
