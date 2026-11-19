import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-eleventh-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('keeps a pending full removal separate from the repaired bank condition',()=>{
 render(<STInitialFour data={data}/>);
 expect(screen.getByText(/82 → 86\/150家/)).toBeVisible();
 expect(screen.getByText(/不等于已经摘帽/,{selector:'section > p'})).toBeVisible();
})
it('shows an approved partial removal without closing the penalty condition',()=>{
 render(<STInitialFour data={data}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002872'}});
 expect(screen.getByText(/已获交易所批准撤销/,{selector:'section > p'})).toBeVisible();
 expect(screen.getByText(/处罚触发的其他ST继续保留/,{selector:'section > p'})).toBeVisible();
 expect(screen.getByText('+13.52%')).toBeVisible();
 fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));
 expect(screen.getByText(/2026专项说明不是2026新增现金/)).toBeVisible();
})
it('keeps deducted revenue distinct and links the already published corrected audit',()=>{
 render(<STInitialFour data={data}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002883'}});
 expect(screen.getByText(/不能用未扣除营收代替规则口径/,{selector:'section > p'})).toBeVisible();
 fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));
 expect(screen.getByText(/6月30日已披露更正后2023审计报告/)).toBeVisible();
})
