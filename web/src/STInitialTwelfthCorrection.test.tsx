import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour,InitialReadingCorrections} from './STInitialFour'
import original from './__fixtures__/initial-twelfth-four.json'
import patch from './__fixtures__/initial-twelfth-correction.json'
afterEach(cleanup)
const data=original as InitialFour
const corrections=patch as InitialReadingCorrections
it('shows a visible correction above the preserved original company account',()=>{
 render(<STInitialFour data={data} corrections={corrections}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'600080'}})
 const aside=screen.getByRole('complementary',{name:'期初说明更正'})
 expect(within(aside).getByText(/6月30日已公开的抵偿安排/)).toBeVisible()
 expect(within(aside).getByText(/这不是现金退款到账/)).toBeVisible()
 expect(within(aside).getByText(/不把8月确认倒填/)).toBeVisible()
 expect(within(aside).getByRole('link',{name:/2026-06-30/})).toHaveAttribute('href',expect.stringContaining('#page=5'))
 expect(within(aside).getByRole('link',{name:/2026-08-22/})).toHaveAttribute('href',expect.stringContaining('#page=25'))
 expect(within(aside).getByText(/以下保留上一版/)).toBeVisible()
 expect(screen.getByText(/86 → 90\/150家/)).toBeVisible()
})
it('does not attach the Ginwa correction to another company',()=>{
 render(<STInitialFour data={data} corrections={corrections}/>);
 expect(screen.queryByRole('complementary',{name:'期初说明更正'})).not.toBeInTheDocument()
})
it('keeps old frozen data readable without a correction packet',()=>{
 render(<STInitialFour data={data}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'600080'}})
 expect(screen.queryByRole('complementary',{name:'期初说明更正'})).not.toBeInTheDocument()
})
