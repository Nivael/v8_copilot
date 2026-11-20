import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour,type InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-eighteenth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value}})
it('retains cohort coverage and separate financial versus audit criteria',()=>{
 render(<STInitialFour data={data} readableAmounts/>);
 expect(screen.getByText(/110 → 114\/150家/)).toBeVisible()
 expect(screen.getAllByText(/财报无保留和内控有效并不消除财务组合约束/)[0]).toBeVisible()
 company('600476');expect(screen.getAllByText(/不写无法表示/)[0]).toBeVisible()
})
it('keeps draft penalty and distinct pre-restructuring votes separate',()=>{
 render(<STInitialFour data={data} readableAmounts/>);company('600525')
 expect(screen.getAllByText(/处罚事先告知/)[0]).toBeVisible()
 company('600537');expect(screen.getAllByText(/借款方案未通过/)[0]).toBeVisible()
 expect(screen.getAllByText(/不写工作日/)[0]).toBeVisible()
 fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'))
 expect(screen.getAllByRole('link',{name:/第16页/})[0]).toHaveAttribute('href',expect.stringContaining('#page=16'))
})
