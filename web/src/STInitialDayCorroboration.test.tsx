import {render,screen,fireEvent,cleanup,within} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STInitialDayCorroboration} from './STInitialDayCorroboration'
import type {InitialDayCorroboration} from './STInitialDayCorroboration'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
import type {RuiheProcess} from './STRuiheProcess'
import day from './__fixtures__/initial-day-corroboration.json'
import initial from './__fixtures__/initial-status-coverage.json'
import ruihe from './__fixtures__/ruihe-process.json'
afterEach(cleanup)
it('区分阅读覆盖、原件身份和完整名录，不把42家冒充全名单认证',()=>{render(<STInitialDayCorroboration data={day as InitialDayCorroboration}/>);expect(screen.getByRole('table',{name:'期初证据的不同覆盖范围'})).toHaveTextContent('20 → 42/150家');expect(screen.getByRole('table',{name:'期初证据的不同覆盖范围'})).toHaveTextContent('本轮新增认证0');expect(screen.getByText(/另外6份主要支持当时身份/)).toBeVisible()})
it('天箭正文旧简称冲突保留，不认定已摘帽',()=>{render(<STInitialDayCorroboration data={day as InitialDayCorroboration}/>);fireEvent.change(screen.getByLabelText('期初当日原件公司'),{target:{value:'002977'}});expect(screen.getByText(/页首写\*ST天箭，异动介绍段却写天箭科技/)).toBeVisible();expect(screen.getByText(/不据旧介绍段认定已摘帽/)).toBeVisible()})
it('保留美丽原件金额格式和嘉应旧制度条款的限制',()=>{render(<STInitialDayCorroboration data={day as InitialDayCorroboration}/>);expect(screen.getByText(/逗号格式异常/)).toBeVisible();fireEvent.change(screen.getByLabelText('期初当日原件公司'),{target:{value:'002198'}});expect(screen.getByText(/不认证规则调整后的交易限制/)).toBeVisible();fireEvent.click(screen.getByText('查看本件原始页码'));expect(screen.getAllByRole('link',{name:/第[123]页/})).toHaveLength(3)})
it('当日补证同窗不删除退出的康佳，也不填期末零收益',()=>{render(<STInitialDayCorroboration data={day as InitialDayCorroboration}/>);fireEvent.click(screen.getByText('这22家从同一起点看，后来走势有何区别？'));const table=screen.getByRole('table',{name:'当日补证22家同窗行情'});expect(within(table).getAllByRole('row')).toHaveLength(23);const row=within(table).getByRole('row',{name:/康佳A/});expect(row).toHaveTextContent('不可算');expect(row).toHaveTextContent('共同日期缺实际成交端点')})
it('最新覆盖完整保留150只，108缺记录、本轮22家都可筛查',()=>{render(<STInitialDayCorroboration data={day as InitialDayCorroboration}/>);fireEvent.click(screen.getByText('现在150只的期初阅读覆盖，哪些还缺？'));const table=screen.getByRole('table',{name:'期初最新150只阅读覆盖'});expect(within(table).getAllByRole('row')).toHaveLength(109);fireEvent.change(screen.getByLabelText('期初最新覆盖筛选'),{target:{value:'new'}});expect(within(table).getAllByRole('row')).toHaveLength(23);fireEvent.change(screen.getByLabelText('期初最新覆盖筛选'),{target:{value:'all'}});expect(within(table).getAllByRole('row')).toHaveLength(151)})
it('新阅读目的默认进入，旧六家当轮20家不冒充当前42家',()=>{render(<STInitialStatusCoverage data={initial as InitialStatusCoverage} ruihe={ruihe as RuiheProcess} day={day as InitialDayCorroboration}/>);expect(screen.getByLabelText('期初专题阅读目的')).toHaveValue('day');fireEvent.change(screen.getByLabelText('期初专题阅读目的'),{target:{value:'baseline'}});expect(screen.getByText(/当前已更新为42\/150、仍缺108家/)).toBeVisible();expect(screen.getByRole('region',{name:'六家期初成员同窗行情'})).toBeVisible()})
