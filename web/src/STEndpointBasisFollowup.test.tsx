import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STEndpointBasisFollowup,type EndpointBasisFollowup} from './STEndpointBasisFollowup'
import {STEndpointSelectionAudit,type EndpointSelectionAudit} from './STEndpointSelectionAudit'
import fixture from './__fixtures__/endpoint-basis-followup.json'
import audit from './__fixtures__/endpoint-selection-audit.json'
afterEach(cleanup)
it('compares both constructions without certifying one shared return or fresh raw data',()=>{
 render(<STEndpointBasisFollowup data={fixture as EndpointBasisFollowup}/>);
 const table=screen.getByRole('table',{name:'两种复权构造与收益'});expect(within(table).getAllByRole('row')).toHaveLength(6);expect(table).toHaveTextContent('10.333551元');expect(table).toHaveTextContent('10.340000元');expect(table).toHaveTextContent('-14.34%');expect(table).toHaveTextContent('-14.33%');
 expect(screen.getByText(/141家直接核价通过的统计保持不变/)).toBeInTheDocument();expect(screen.getByText(/本轮新取得原价响应0份/)).toBeInTheDocument();
 fireEvent.click(screen.getByText('绝味这个例子，计算怎样接回原件？'));
 expect(screen.getByText(/精确虚拟值约0.2464869749元/)).toBeInTheDocument();expect(screen.getByRole('link',{name:'绝味权益分派原件 · 第2页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-10-19/1225610029.PDF#page=2');
})
it('labels explained differences separately while still withholding certification',()=>{
 render(<STEndpointSelectionAudit data={audit as EndpointSelectionAudit} basisExplained/>);
 const table=screen.getByRole('table',{name:'成交与核价范围'});expect(table).toHaveTextContent('直接报价不等');expect(table).toHaveTextContent('141');
 fireEvent.click(screen.getByText('保留全部150家及每家的核验状态'));
 expect(within(screen.getByRole('table',{name:'全量150家认证收益'})).getAllByText('直接报价不等，留空')).toHaveLength(5);
})
