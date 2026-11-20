import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-fourteenth-four.json'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
import initialStatus from './__fixtures__/initial-status-coverage.json'
afterEach(cleanup)
const data=fixture as InitialFour
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value}})
it('separates completed restatement from the punishment clock',()=>{
 render(<STInitialFour data={data}/> )
 expect(screen.getByText(/94 → 98\/150家/)).toBeVisible()
 expect(screen.getByText(/不将3月20日收到日当作出日或自动摘帽日/)).toBeVisible()
})
it('keeps approved star removal and repair distinct from a new emphasis matter',()=>{
 render(<STInitialFour data={data}/>);company('600165')
 expect(screen.getByText(/1月14日生效，其他风险警示保留/)).toBeVisible()
 expect(screen.getByText(/不把新强调事项当保留意见或自动ST原因/)).toBeVisible()
 expect(screen.getByText(/宁科240\/242末页HTTP403两次，2条缺口保持/)).toBeVisible()
})
it('does not call an out-of-court proposal an accepted judicial reorganization',()=>{
 render(<STInitialFour data={data}/>);company('600180')
 expect(screen.getByText(/自主协商不具司法强制效力/)).toBeVisible()
 fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'))
 expect(screen.getByRole('link',{name:/2025年度审计报告 · 第4页/})).toHaveAttribute('href',expect.stringContaining('#page=4'))
})
it('defaults to the latest batch and keeps one common early window',()=>{
 render(<STInitialStatusCoverage data={initialStatus as InitialStatusCoverage} fourteenthFour={data}/> )
 expect(screen.getByRole('heading',{name:'重整、处罚和审计，分别修复了什么？'})).toBeVisible()
 expect(document.querySelector('#st-initial-status-coverage > p')).toHaveTextContent('2026-11-19')
 fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}})
 expect(screen.getByText(/2026-07-31 · 20个交易日/)).toBeVisible()
 expect(within(screen.getByRole('table',{name:'期初四家风险与同窗表现'})).getAllByRole('row')).toHaveLength(5)
})
