import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STExitOutcomes} from './STExitOutcomes'
import data from './__fixtures__/exit-outcomes.json'
afterEach(cleanup)
it('keeps all 14 and switches fixed-window return denominators',()=>{
 render(<STExitOutcomes data={data}/>);const table=screen.getByRole('table');expect(within(table).getAllByRole('row')).toHaveLength(15);expect(screen.getByText(/12家撤销警示公司：/)).toHaveTextContent('12家通过本窗口核价，1家上涨');
 fireEvent.change(screen.getByRole('combobox'),{target:{value:'full'}});expect(screen.getByText(/12家撤销警示公司：/)).toHaveTextContent('11家通过本窗口核价，2家上涨');expect(table).toHaveTextContent('报价待核，留空');expect(table).toHaveTextContent('缺成交端点，留空');expect(screen.getByText('不是各自摘帽后的收益')).toBeVisible();
})
it('separates delisting-period start from final removal and retains original evidence',()=>{
 render(<STExitOutcomes data={data}/>);fireEvent.click(screen.getByRole('button',{name:'萃华 002731'}));expect(screen.getByText(/7月3日仍因年报事项停牌/)).toHaveTextContent('11月13日摘牌');expect(screen.getByRole('table')).toHaveTextContent('2026-10-23 · 进入退市整理（非摘牌日）');
 fireEvent.click(screen.getByText('展开所选公司的公告依据'));expect(screen.getAllByRole('link').length).toBeGreaterThan(2);expect(screen.getByText(data.selection_boundary)).toHaveTextContent('岭南');
})
