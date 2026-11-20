import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STBailiPolicyFollowup} from './STBailiPolicyFollowup'
import {STRestatementComparison} from './STRestatementComparison'
import data from './__fixtures__/baili-policy-followup.json'
import comparison from './__fixtures__/restatement-comparison.json'
afterEach(cleanup)
it('shows timing conflict and distinguishes tax estimation from cash and certification',()=>{
 render(<STBailiPolicyFollowup data={data}/>);expect(screen.getByText(data.answer)).toHaveTextContent('原半年报已提及该政策');
 fireEvent.click(screen.getByText('按日期看：政策、半年报与更正'));
 const table=screen.getByRole('table');expect(table).toHaveTextContent('2026-07-17');expect(table).toHaveTextContent('2026-08-28');expect(table).toHaveTextContent('2026-08-31');
 expect(within(table).getByRole('link',{name:'原件第190页'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-08-31/1225534310.PDF#page=190');
 fireEvent.click(screen.getByText('消费税与递延所得税资产，怎样联系起来？'));
 expect(screen.getByText(data.mechanism)).toHaveTextContent('不是把消费税税率直接乘半年利润');
 expect(screen.getByText(/这次调整不是当期已缴税款/)).toBeInTheDocument();
})
it('extends the existing comparison without changing stock windows',()=>{
 render(<STRestatementComparison data={comparison} baili={data}/>);
 expect(screen.getByRole('region',{name:'百利政策与更正续核'})).toBeInTheDocument();
 fireEvent.change(screen.getByRole('combobox'),{target:{value:'20'}});
 const table=screen.getByRole('table',{name:/统一从10月27日/});expect(table).toHaveTextContent('17日，窗口未满');expect(table).toHaveTextContent('—（无共同成交端点）');
})
