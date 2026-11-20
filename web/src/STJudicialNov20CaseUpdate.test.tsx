import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {STJudicialNov20CaseUpdate,judicialNov20CaseBound} from './STJudicialNov20CaseUpdate'
import xilinmen from './__fixtures__/twentysecond-period-followup.json'
import ruimao from './__fixtures__/fourteenth-period-followup.json'
afterEach(cleanup)
it.each([['603008',xilinmen,'拍卖公示不能当作上市公司已经回款'],['600180',ruimao,'不能直接加到原债权或亏损上']] as const)('connects the new disclosure to existing %s questions', (code,context,text)=>{
 expect(judicialNov20CaseBound(code,context)).toBe(true)
 const before=JSON.stringify(context)
 render(<STJudicialNov20CaseUpdate code={code} context={context}/>);
 expect(screen.getByRole('complementary')).toHaveTextContent(text)
 expect(JSON.stringify(context)).toBe(before)
})
it.each(['source','chain'])('rejects a changed existing %s',kind=>{
 const context=structuredClone(xilinmen)
 if(kind==='source')context.sources.find(s=>s.symbol==='603008')!.sha256='changed'
 else context.chains.find(c=>c.chain.startsWith('603008-'))!.open='changed'
 render(<STJudicialNov20CaseUpdate code="603008" context={context}/>);
 expect(screen.getByRole('status')).toHaveTextContent('暂不接入新解释')
})
