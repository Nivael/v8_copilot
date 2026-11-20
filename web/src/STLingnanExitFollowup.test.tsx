import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STEndpointReasons,type EndpointReasons} from './STEndpointReasons'
import {STLingnanExitFollowup,type LingnanExitFollowup} from './STLingnanExitFollowup'
import fixture from './__fixtures__/lingnan-exit-followup.json'
import endpoints from './__fixtures__/endpoint-reasons.json'
afterEach(cleanup)
it('opens the later evidence from the existing missing-endpoint case',()=>{
 render(<STEndpointReasons data={endpoints as EndpointReasons} lingnan={fixture as LingnanExitFollowup}/>);
 expect(screen.queryByRole('region',{name:'岭南退出与更正判断更新'})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'本轮补核岭南：触发、更正与最终退出 →'}));
 const region=screen.getByRole('region',{name:'岭南退出与更正判断更新'});expect(region).toHaveTextContent('尚未取得可认证的最终决定或摘牌日');expect(within(region).getByRole('table',{name:'岭南程序与披露时间线'})).toHaveTextContent('2026-10-16');expect(region).toHaveTextContent('披露2026-10-17');
 expect(within(region).getByText(/2025年8月25日，不是2026年11月最新余额/)).toBeInTheDocument();
})
it('separates consolidated equity, parent equity and unreported quarterly cash',()=>{
 render(<STLingnanExitFollowup data={fixture as LingnanExitFollowup}/>);
 fireEvent.click(screen.getByText('看清财报更正的具体金额与范围'));
 expect(screen.getByRole('table',{name:'岭南2025年更正金额'})).toHaveTextContent('-129,738.43万元');
 expect(screen.getByText(/不能替换三季报比较栏的2025年末归母权益/)).toBeInTheDocument();
 fireEvent.click(screen.getByText('季度亏损、累计现金与时点分别怎样？'));
 const table=screen.getByRole('table',{name:'岭南单季与累计经营'});expect(within(table).getByText('未直接披露')).toBeInTheDocument();expect(table).toHaveTextContent('2,659.05万元');expect(screen.getByText(/不能把后来信息倒填成9月末已知/)).toBeInTheDocument();
})
