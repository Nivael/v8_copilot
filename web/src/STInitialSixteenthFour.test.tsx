import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-sixteenth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('keeps the original amount conflict visible and sources inspectable',()=>{
 render(<STInitialFour data={data}/> )
 expect(screen.getByText(/102 → 106\/150家/)).toBeVisible()
 expect(screen.getAllByText(/原件单位冲突/)[0]).toBeVisible()
 expect(screen.getAllByRole('link',{name:/第2页/})[0]).toHaveAttribute('href',expect.stringContaining('#page=2'))
})
it('lets readers compare stages without treating repair as removal',()=>{
 render(<STInitialFour data={data}/> )
 fireEvent.change(screen.getByLabelText('选择公司核对期初原件'),{target:{value:'600302'}})
 expect(screen.getAllByText(/不能据此宣告内控有效或摘帽/)[0]).toBeVisible()
 fireEvent.change(screen.getByLabelText('选择公司核对期初原件'),{target:{value:'600337'}})
 expect(screen.getAllByText(/两主体分开/)[0]).toBeVisible()
 fireEvent.click(screen.getByText('共同价格端点，跨渠道核到哪一步？'))
 expect(screen.getByText(/12个实际股票端点两源一致/)).toBeVisible()
})
