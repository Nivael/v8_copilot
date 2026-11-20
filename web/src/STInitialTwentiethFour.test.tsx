import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour,type InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-twentieth-four.json'
afterEach(cleanup)
const company=(value:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value}})
it('distinguishes partial receipts, remaining warnings, and audit verification',()=>{
 render(<STInitialFour data={fixture as InitialFour}/>);
 expect(screen.getByText(/118 → 122\/150家/)).toBeVisible()
 expect(screen.getAllByText(/首笔已收、后续待履行/)[0]).toBeVisible()
 company('600734');expect(screen.getAllByText(/争取目标，尚非结果/)[0]).toBeVisible()
 company('600745');expect(screen.getAllByText(/不能改写为审计已确认问题消除/)[0]).toBeVisible()
})
it('exposes conflicting source values with original identity mapping',()=>{
 render(<STInitialFour data={fixture as InitialFour}/>);company('600735')
 fireEvent.click(screen.getByText('来源有冲突：查看采用依据与保留的异值'))
 expect(screen.getByText(/首次立案公告1224984682第1页支持/)).toBeVisible()
 expect(screen.getByText(/按首次公告分别建主体/)).toBeVisible()
 expect(screen.getByText(/其他来源公司编号：0242026003/)).toBeVisible()
})

it("keeps a million-yuan receipt readable in ten-thousands",()=>{render(<STInitialFour data={fixture as InitialFour} readableAmounts/>);expect(screen.getByText(/约101.23万元实收/)).toBeVisible()})
