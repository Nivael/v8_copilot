import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STInitialFour} from './STInitialFour'
import type {InitialFour} from './STInitialFour'
import fixture from './__fixtures__/initial-tenth-four.json'
afterEach(cleanup)
const data=fixture as InitialFour
it('keeps the halted and exited stock in the same comparison with an explained null',()=>{
 render(<STInitialFour data={data}/>);
 expect(screen.getByText(/78 → 82\/150家/)).toBeVisible();
 const table=screen.getByRole('table',{name:'期初四家风险与同窗表现'});
 expect(within(table).getByText('缺价，保留空值')).toBeVisible();
 expect(within(table).getByText(/起点与期末均缺/)).toBeVisible();
 fireEvent.change(screen.getByRole('combobox',{name:'期初四家比较窗口'}),{target:{value:'early20'}});
 expect(within(table).getByText('缺价，保留空值')).toBeVisible();
})
it('shows actual endpoint conflicts without certifying all twelve or new index checks',()=>{
 render(<STInitialFour data={data}/>);
 fireEvent.click(screen.getByText('共同价格端点，跨渠道核到哪一步？'));
 expect(screen.getByText(/本轮不新增指数端点认证/)).toBeVisible();
 const table=screen.getByRole('table',{name:'共同端点缺失与冲突'});
 expect(within(table).getAllByText('两渠道均无实际成交端点')).toHaveLength(2);
 expect(within(table).getByText('前复权基准冲突')).toBeVisible();
 expect(screen.queryByText(/四股12个前复权共同端点已/)).not.toBeInTheDocument();
})
it('changes the question evidence when selecting an application case',()=>{
 render(<STInitialFour data={data}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002789'}});
 expect(screen.getByText(/申请撤销退市风险警示后仍需其他ST/,{selector:'section > p'})).toBeVisible();
 fireEvent.click(screen.getByText('查看警示依据、修复披露与日期'));
 expect(screen.getByText(/补充材料阶段，申请尚需批准/)).toBeVisible();
})

it('separates later exit evidence from the halted initial state',()=>{
 render(<STInitialFour data={data}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'选择公司核对期初原件'}),{target:{value:'002731'}});
 fireEvent.click(screen.getByText('后来为什么缺价？查看退出公告'));
 expect(screen.getByText(/以下为期初之后的新事实，不能倒填期初/)).toBeVisible();
 expect(screen.getByRole('link',{name:/2026-11-13.*终止上市暨摘牌/})).toBeVisible();
})
