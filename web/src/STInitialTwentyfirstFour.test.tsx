import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour,type InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-twentyfirst-four.json'
afterEach(cleanup)
it('keeps partial removal, noncash return, and deducted revenue distinct',()=>{
 render(<STInitialFour data={fixture as InitialFour}/>);
 expect(screen.getByText(/122 → 126\/150家/)).toBeVisible()
 expect(screen.getAllByText(/不消除财务虚假记载处罚/)[0]).toBeVisible()
 const company=(code:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:code}})
 company('600818');expect(screen.getAllByText(/不能直接写现金到账/)[0]).toBeVisible()
 company('600889');expect(screen.getAllByText(/扣除后263638261.84元/)[0]).toBeVisible()
})
it('links the company regulator original at its verified decision date',()=>{
 render(<STInitialFour data={fixture as InitialFour}/>);
 fireEvent.click(screen.getByText('处罚决定的作出日期，核公司本体监管原件'))
 expect(screen.getByRole('link',{name:/福建海钦能源集团股份有限公司 · 正文落款2026-04-28/})).toHaveAttribute('href','https://www.csrc.gov.cn/fujian/c104064/c7630084/content.shtml')
})
