import {render,screen,fireEvent,cleanup,within} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STInitialWarningOrigin} from './STInitialWarningOrigin'
import type {InitialWarningOrigin} from './STInitialWarningOrigin'
import {STInitialDayCorroboration} from './STInitialDayCorroboration'
import type {InitialDayCorroboration} from './STInitialDayCorroboration'
import origin from './__fixtures__/initial-warning-origin.json'
import day from './__fixtures__/initial-day-corroboration.json'
afterEach(cleanup)
it('先解释不同警示条件，七家公司比较不冒充七次验证',()=>{render(<STInitialWarningOrigin data={origin as InitialWarningOrigin}/>);expect(within(screen.getByRole('table',{name:'七家公司期初警示条件比较'})).getAllByRole('row')).toHaveLength(8);expect(screen.getByText(/阅读覆盖仍为42\/150、另108家/)).toBeVisible()})
it('沈化已收到最终处罚，仍不能用收到日推摘帽',()=>{render(<STInitialWarningOrigin data={origin as InitialWarningOrigin}/>);fireEvent.change(screen.getByLabelText('期初警示依据公司'),{target:{value:'000698'}});expect(screen.getByText(/4月进展已称收到最终处罚/)).toBeVisible();expect(screen.getByText(/不能用收到日自动算摘帽日/)).toBeVisible();fireEvent.click(screen.getByText('原始警示与进展：按披露时间核原文'));expect(screen.getAllByRole('link')).toHaveLength(4);expect(screen.getAllByText(/目录日期按北京时间/)).toHaveLength(2)})
it('天箭更名已有依据但七月原件冲突未解释',()=>{render(<STInitialWarningOrigin data={origin as InitialWarningOrigin}/>);fireEvent.change(screen.getByLabelText('期初警示依据公司'),{target:{value:'002977'}});expect(screen.getByText(/4月24日天箭科技更名\*ST天箭/)).toBeVisible();expect(screen.getByText(/7月异动原件内部差异未被更正解释/)).toBeVisible()})
it('去星仍留ST与能特未来升级条件分开',()=>{render(<STInitialWarningOrigin data={origin as InitialWarningOrigin}/>);fireEvent.change(screen.getByLabelText('期初警示依据公司'),{target:{value:'002586'}});expect(screen.getByText(/2025年12月撤销退市及部分其他风险警示/)).toBeVisible();fireEvent.change(screen.getByLabelText('期初警示依据公司'),{target:{value:'002102'}});expect(screen.getByText(/不是已经\*ST/)).toBeVisible()})
it('复用七月共同起点，康佳缺价继续留表',()=>{render(<STInitialWarningOrigin data={origin as InitialWarningOrigin}/>);fireEvent.click(screen.getByText('这七家后来走势，与ST和大盘同窗看'));const t=screen.getByRole('table',{name:'七家警示条件与同窗行情'});expect(within(t).getAllByRole('row')).toHaveLength(8);expect(within(t).getByRole('row',{name:/康佳/})).toHaveTextContent('不可算');expect(screen.getByText(/不拿7月收益冒充实施警示后的收益/)).toBeVisible();expect(screen.getByText(/沈化完整段上涨、围海下跌/)).toBeVisible()})
it('与旧原件说明衔接，历史六件缺原因不冒充当前缺口',()=>{render(<STInitialDayCorroboration data={day as InitialDayCorroboration} origin={origin as InitialWarningOrigin}/>);fireEvent.click(screen.getByText('回看22份异动原件，或查150只阅读缺口'));expect(screen.getByText(/本轮已补六家的前置警示依据/)).toBeVisible();fireEvent.change(screen.getByLabelText('期初当日原件公司'),{target:{value:'002977'}});expect(screen.getByText(/该公司警示依据本轮已补/)).toBeVisible();expect(screen.getByText(/内部简称冲突：页首/)).toBeVisible()})
