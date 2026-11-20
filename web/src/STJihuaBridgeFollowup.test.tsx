import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {STJihuaBridgeFollowup} from './STJihuaBridgeFollowup'
import data from './__fixtures__/jihua-bridge-followup.json'
afterEach(cleanup)
it('retains direct and derived quarters and labels implied values',()=>{
 render(<STJihuaBridgeFollowup data={data}/>);
 expect(screen.getByText(data.answer)).toHaveTextContent('完整调节尚未确认');
 fireEvent.click(screen.getByText('展开三项原数与衔接计算'));
 expect(screen.getByRole('table')).toHaveTextContent('40,672.56元');expect(screen.getByRole('table')).toHaveTextContent('38,852.53元');expect(screen.getByRole('table')).toHaveTextContent('38,952.53元');
 fireEvent.click(screen.getByText('倒推可比半年值：只能当核查线索'));
 expect(screen.getAllByText(/非披露值/)).toHaveLength(3);
})
it('does not turn matching residual into a second validation or full reconciliation',()=>{
 render(<STJihuaBridgeFollowup data={data}/>);fireEvent.click(screen.getByText('100元差异，怎样接回非经常性损益？'));
 expect(screen.getByText(/比直接单季/)).toHaveTextContent('少100元');expect(screen.getByText(/不是另一次独立验证/)).toBeVisible();
 fireEvent.click(screen.getByText('查看两份原报告及页码'));expect(screen.getAllByRole('link')).toHaveLength(6);
})
