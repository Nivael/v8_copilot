import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour,type InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-twentyseventh-four.json'
afterEach(cleanup)
it('keeps coverage boundary and source document identity visible',()=>{
 render(<STInitialFour data={fixture as InitialFour} readableAmounts/>);
 expect(screen.getByText(/146 → 150\/150家/)).toBeVisible()
 expect(screen.getByText(/150\/150仅表示/)).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'603959'}})
 fireEvent.click(screen.getByText('来源有冲突：查看采用依据与保留的异值'))
 expect(screen.getByText(/不重复算作独立内控意见/)).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'605199'}})
 expect(screen.getAllByText(/明确限定用途/)[0]).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'605336'}})
 expect(screen.getAllByText(/不涉及既往年报、现金流或盈亏性质变化/)[0]).toBeVisible()
})
