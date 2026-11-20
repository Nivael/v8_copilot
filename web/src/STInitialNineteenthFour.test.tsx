import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour,type InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-nineteenth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value}})
it('shows coverage and readable financial units without replacing audit criteria',()=>{
 render(<STInitialFour data={data} readableAmounts/>);
 expect(screen.getByText(/114 → 118\/150家/)).toBeVisible()
 expect(screen.getByText(/营业收入约2.04亿元/)).toBeVisible()
 expect(screen.getByText(/营业收入203524209.34元/)).not.toBeVisible()
})
it('keeps failed enforcement and completed disposal separate from pending financing',()=>{
 render(<STInitialFour data={data} readableAmounts/>);company('600568')
 expect(screen.getAllByText(/终结本次执行程序/)[0]).toBeVisible()
 company('600581');expect(screen.getAllByText(/交易所审核与证监会注册/)[0]).toBeVisible()
 expect(screen.getAllByText(/焦煤不再并表/)[0]).toBeVisible()
 expect(screen.getByText(/加少数股东权益约0.61亿元/)).toBeVisible()
})
it('links company regulator originals without substituting individual penalties',()=>{
 render(<STInitialFour data={data}/>);
 fireEvent.click(screen.getByText('处罚决定的作出日期，核公司本体监管原件'))
 expect(screen.getByRole('link',{name:/上海复旦复华科技股份有限公司 · 正文落款2025-12-26/})).toHaveAttribute('href','https://www.csrc.gov.cn/shanghai/c103864/c7610000/content.shtml')
 company('600624');expect(screen.getByText(/不是从事先告知日计时或届时自动撤销/)).toBeVisible()
})
