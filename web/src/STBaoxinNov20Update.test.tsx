import {afterEach,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {STBaoxinNov20Update,baoxinNov20Bound} from './STBaoxinNov20Update'
import context from './__fixtures__/baoxin-holding-bridge.json'
afterEach(cleanup)
it('connects a new failed auction without replacing old registration facts',()=>{
 expect(baoxinNov20Bound(context)).toBe(true)
 render(<STBaoxinNov20Update context={context}/>);
 expect(screen.getByRole('complementary')).toHaveTextContent('不能因股数同为200万')
 expect(screen.getByRole('complementary')).toHaveTextContent('关系仍未核清')
 expect(screen.getByRole('complementary')).toHaveTextContent('没有证明此前抵债股份登记完成')
})
it.each(['rows','sources','debt'])('withholds the link when old %s evidence changes',key=>{
 const changed=structuredClone(context)
 if(key==='rows')changed.rows[0].registered_shares++
 else if(key==='sources')changed.sources[0].sha256='different'
 else changed.debt.registered=!changed.debt.registered
 render(<STBaoxinNov20Update context={changed}/>);
 expect(screen.getByRole('status')).toHaveTextContent('暂不接入新解释')
 expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
})
