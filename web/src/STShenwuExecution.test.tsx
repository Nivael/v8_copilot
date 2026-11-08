import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STShenwuExecution} from './STShenwuExecution'
import raw from './__fixtures__/shenwu-execution.json'
import type {RegimeShenwuExecution} from './stRegimeTypes'
afterEach(cleanup)
const data=raw as unknown as RegimeShenwuExecution
it('answers separately for shareholder shares, consortium scope and an older subsidiary receivable',()=>{
 render(<STShenwuExecution data={data}/>);expect(screen.getByRole('heading',{name:'过户、签约，距离现金到账还有多远？'})).toBeVisible()
 expect(screen.getByRole('rowheader',{name:'股东3300万股'})).toBeVisible();expect(screen.getByText(/含税暂定总价7.17亿元/)).toBeVisible();expect(screen.getByText(/应结算1,325.05万元/)).toBeVisible()
 expect(screen.getByText(/此后是否到账尚未核实/)).toBeVisible()
 expect(screen.getByText(/若后续合同解除或撤销.*不抹去已签约的历史事实/)).toBeVisible()
})
it('retains auction stages and the explicit year conflict without treating repeated reports as new cases',()=>{
 render(<STShenwuExecution data={data}/>);fireEvent.click(screen.getByText('股东股份：两次流拍怎样推进到过户？'));fireEvent.click(screen.getByText('核累计股数分母，以及8月公告的一处年份冲突'))
 expect(screen.getByText(/2026-07-05至2026-07-06/)).toBeVisible();expect(screen.getByText(/2025-07-07.*2026-07-07/)).toBeVisible();expect(screen.getByText(/三个文件旁证同一件事/)).toBeVisible()
 expect(screen.getByText(/不拿股票市价乘股数充当公司收到的现金/)).toBeVisible()
})
it('does not treat the signing date as publication or the planned completion as actual start',()=>{
 render(<STShenwuExecution data={data}/>);fireEvent.click(screen.getByText('7.17亿元合同：已经签了什么，哪些仍待兑现？'))
 expect(screen.getByText(/2026-10-26订立.*2026-10-27签署.*2026-10-28公开/)).toBeVisible()
 expect(screen.getByText(/71,712.00万元.*265.00.*67,721.04.*3,725.96/)).toBeVisible();expect(screen.getByText(/未核实际开工日/)).toBeVisible()
})
it('changes equal windows and keeps two immature twenty-day observations empty',()=>{
 render(<STShenwuExecution data={data}/>);fireEvent.click(screen.getByText('公告之后，个股与大盘/ST怎样走？'))
 expect(screen.getAllByText('-5.99%')).toHaveLength(1);fireEvent.change(screen.getByRole('combobox',{name:'神雾执行公告窗口'}),{target:{value:'20'}})
 expect(screen.getByText('+48.43%')).toBeVisible();expect(screen.getAllByText('窗口未满或缺成交端点')).toHaveLength(6)
})
it('keeps legacy snapshots free of invented execution facts',()=>{const {container}=render(<STShenwuExecution data={null}/>);expect(container).toBeEmptyDOMElement()})
