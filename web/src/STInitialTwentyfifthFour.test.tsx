import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour,type InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-twentyfifth-four.json'
afterEach(cleanup)
it('keeps audit scope and unresolved dates visible across company changes',()=>{
 render(<STInitialFour data={fixture as InitialFour} readableAmounts/>);
 expect(screen.getByText(/138 → 142\/150家/)).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'603789'}})
 expect(screen.getAllByText(/9月29日/)[0]).toBeVisible()
 expect(screen.getAllByText(/持续经营/)[0]).toBeVisible()
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'603825'}})
 expect(screen.getAllByText(/两份原始公告由官方PDF补回/)[0]).toBeVisible()
 expect(screen.queryByText('主源值，跨源待核')).toBeNull()
})
