import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STJingjiDividendFollowup} from './STJingjiDividendFollowup'
import data from './__fixtures__/jingji-dividend-followup.json'
afterEach(cleanup)
it('shows unequal exact paths with identical rounded outcomes without claiming unique input',()=>{
 render(<STJingjiDividendFollowup data={data}/>);const table=screen.getByRole('table',{name:/换股价从14.50/});expect(table).toHaveTextContent('14.4673312元');expect(table).toHaveTextContent('14.467元');expect(within(table).getAllByText('14.47元')).toHaveLength(2);expect(screen.getByText(/第二行是本轮敏感性对照/)).toBeVisible();
})
it('preserves printed denominator and exact truncation and original page links',()=>{
 render(<STJingjiDividendFollowup data={data}/>);fireEvent.click(screen.getByText('展开原式分母、总股本与截取精度'));const table=screen.getByRole('table',{name:/同用公告印刷现金总额/});expect(table).toHaveTextContent('616,624,778股');expect(table).toHaveTextContent('0.329999元');expect(table).toHaveTextContent('622,874,778股');expect(table).toHaveTextContent('0.326688元');fireEvent.click(screen.getByText('查看两份发行人原件与页码'));expect(screen.getAllByRole('link')).toHaveLength(3);expect(screen.getByRole('link',{name:'第3页'})).toHaveAttribute('href','https://static.cninfo.com.cn/finalpage/2026-06-30/1225394064.PDF#page=3');
})
