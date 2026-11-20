import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour,type InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-twentythird-four.json'
afterEach(cleanup)
it('separates audit opinions from thresholds and remaining warnings',()=>{
 render(<STInitialFour data={fixture as InitialFour}/>);
 expect(screen.getByText(/130 → 134\/150家/)).toBeVisible()
 expect(screen.getAllByText(/无保留不代替财务门槛满足/)[0]).toBeVisible()
 const company=(code:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:code}})
 company('603359');expect(screen.getAllByText(/6月30日仍核查延期/)[0]).toBeVisible()
 company('603377');expect(screen.getAllByText(/预重整不是法院正式受理/)[0]).toBeVisible()
 company('603378');expect(screen.getAllByText(/不能全部视为可用现金/)[0]).toBeVisible()
})
