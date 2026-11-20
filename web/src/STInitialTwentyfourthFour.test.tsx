import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour,type InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-twentyfourth-four.json'
afterEach(cleanup)
it('retains quote conflict original values and partial payment limits',()=>{
 render(<STInitialFour data={fixture as InitialFour}/>);
 expect(screen.getByText(/134 → 138\/150家/)).toBeVisible()
 expect(screen.getByText('主源值，跨源待核')).toBeVisible()
 fireEvent.click(screen.getByText('共同价格端点，跨渠道核到哪一步？'))
 expect(screen.getAllByText('价格精度或复权口径待核')).toHaveLength(2)
 expect(screen.getByText('10.333550689276564')).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'603595'}})
 expect(screen.getAllByText(/余90%按约2026—2028年分期/)[0]).toBeVisible()
})
