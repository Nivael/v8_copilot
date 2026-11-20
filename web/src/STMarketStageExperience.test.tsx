import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {STMarketStageExperience} from './STMarketStageExperience'
import data from './__fixtures__/market-stage-experience.json'
afterEach(cleanup)
it('switches denominators while market references stay unchanged',()=>{
 render(<STMarketStageExperience data={data}/>);const table=screen.getByRole('table',{name:/动态ST参考/});expect(table).toHaveTextContent('20／142');expect(table).toHaveTextContent('122／145');expect(table).toHaveTextContent('-13.92%');
 fireEvent.click(screen.getByRole('checkbox'));expect(table).toHaveTextContent('20／139');expect(table).toHaveTextContent('118／139');expect(table).toHaveTextContent('-13.92%');expect(screen.getByText(data.common_sample_boundary)).toBeVisible();
})
it('keeps all members and null prices when changing stage',()=>{
 render(<STMarketStageExperience data={data}/>);fireEvent.click(screen.getByText('查看每段分母和全部150家核验状态'));
 const table=screen.getByRole('table',{name:'全部150家逐段核验，缺值保留'});expect(within(table).getAllByRole('row')).toHaveLength(151);expect(table).toHaveTextContent('不计算');
 fireEvent.change(screen.getByRole('combobox'),{target:{value:'4'}});expect(within(table).getAllByRole('row')).toHaveLength(151);expect(screen.getByText(/原样本150家；主源/)).toHaveTextContent('跨源核价通过147家');
 fireEvent.click(screen.getByText('来源、检验边界与证伪条件'));expect(screen.getByText(data.not_established)).toHaveTextContent('不是五次独立制度试验');
})
