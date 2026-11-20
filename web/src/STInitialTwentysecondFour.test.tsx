import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour,type InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-twentysecond-four.json'
afterEach(cleanup)
it('separates audit limitations, notice and preliminary balances',()=>{
 render(<STInitialFour data={fixture as InitialFour}/>);
 expect(screen.getByText(/126 → 130\/150家/)).toBeVisible()
 const company=(code:string)=>fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:code}})
 company('601718');expect(screen.getAllByText(/无保留附强调事项/)[0]).toBeVisible()
 company('603008');expect(screen.getAllByText(/不能机械相加当确定损失/)[0]).toBeVisible()
})
it('keeps original and conflicting Wenfeng years visible on demand',()=>{
 render(<STInitialFour data={fixture as InitialFour}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'601010'}})
 fireEvent.click(screen.getByText('来源有冲突：查看采用依据与保留的异值'))
 expect(screen.getByText(/采用原件日期，冲突及原始文本保留/)).toBeVisible()
 expect(screen.getByText(/2025年4月29日（后续引用）/)).toBeVisible()
})
