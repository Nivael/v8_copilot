import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STEndpointSelectionAudit,type EndpointSelectionAudit} from './STEndpointSelectionAudit'
import fixture from './__fixtures__/endpoint-selection-audit.json'
afterEach(cleanup)
it('distinguishes paired endpoints, quote verification and missing members',()=>{
 render(<STEndpointSelectionAudit data={fixture as EndpointSelectionAudit}/>);
 const table=screen.getByRole('table',{name:'成交与核价范围'});
 expect(within(table).getByText('146')).toBeInTheDocument();expect(within(table).getByText('141')).toBeInTheDocument();expect(within(table).getByText('5')).toBeInTheDocument();expect(within(table).getByText('4')).toBeInTheDocument();
 fireEvent.click(screen.getByText('保留全部150家及每家的核验状态'));
 const all=screen.getByRole('table',{name:'全量150家认证收益'});
 expect(within(all).getAllByRole('row')).toHaveLength(151);expect(within(all).getAllByText('报价待核，留空')).toHaveLength(5);expect(within(all).getAllByText('端点不足，留空')).toHaveLength(4);
 expect(within(all).getByText(/000016/)).toBeInTheDocument();expect(within(all).getByText(/002731/)).toBeInTheDocument();
})
it('does not resolve old July conflicts when the recent window passes',()=>{
 render(<STEndpointSelectionAudit data={fixture as EndpointSelectionAudit}/>);
 fireEvent.change(screen.getByRole('combobox',{name:'全量核价观察窗口'}),{target:{value:'recent'}});
 const table=screen.getByRole('table',{name:'成交与核价范围'});expect(within(table).getAllByText('147')).toHaveLength(2);expect(within(table).getByText('0')).toBeInTheDocument();
 fireEvent.click(screen.getByText('哪些报价仍待核？查看两源原值'));
 expect(screen.getByText(/完整区间的起点差异没有因此解除/)).toBeInTheDocument();
 expect(screen.getByRole('table',{name:'期末状态分组对照'})).toHaveTextContent('136');expect(screen.getByRole('table',{name:'期末状态分组对照'})).toHaveTextContent('14');
})
