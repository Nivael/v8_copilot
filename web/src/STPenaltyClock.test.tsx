import {render,screen,fireEvent,cleanup,within} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STPenaltyClock} from './STPenaltyClock'
import type {PenaltyClock} from './STPenaltyClock'
import {STInitialWarningOrigin} from './STInitialWarningOrigin'
import type {InitialWarningOrigin} from './STInitialWarningOrigin'
import clock from './__fixtures__/penalty-clock.json'
import origin from './__fixtures__/initial-warning-origin.json'
afterEach(cleanup)
it('作出、收到、一周年分开，19日不是自动摘帽倒计时',()=>{render(<STPenaltyClock data={clock as PenaltyClock}/>);const t=screen.getByRole('table',{name:'两家公司处罚日期与当时状态'});expect(within(t).getAllByRole('row')).toHaveLength(3);expect(t).toHaveTextContent('2025-11-25');expect(t).toHaveTextContent('2025-11-28');expect(screen.getByText(/还差19个自然日/)).toBeVisible()})
it('围海申请和生效分开，不猜独立核准函和延迟原因',()=>{render(<STPenaltyClock data={clock as PenaltyClock}/>);expect(screen.getByText(/相隔105个自然日/)).toHaveTextContent('124日');expect(screen.getByText(/本轮也未取得独立核准函/)).toBeVisible();expect(screen.getByText(/2026-08-13披露已提交/)).toBeVisible()})
it('停牌公告窗留空，生效与申请使用各自同窗',()=>{render(<STPenaltyClock data={clock as PenaltyClock}/>);fireEvent.click(screen.getByText('同一事件窗口：申请披露、生效与停牌边界'));const t=screen.getByRole('table',{name:'围海程序节点与同期市场'});expect(within(t).getAllByRole('row')).toHaveLength(4);expect(within(t).getByRole('row',{name:/停牌/})).toHaveTextContent('不可算');expect(t).toHaveTextContent('2026-08-31')})
it('监管网页元数据不冒充决定日，原件页码可展开',()=>{render(<STPenaltyClock data={clock as PenaltyClock}/>);fireEvent.click(screen.getByText('看处罚决定、申请及撤销原件'));expect(screen.getAllByText(/不当决定日或最早历史公开时间/)).toHaveLength(2);expect(screen.getByRole('link',{name:'ST沈化 · 监管机关最终决定 ↗'})).toHaveAttribute('href','https://www.csrc.gov.cn/liaoning/c103750/c7598233/content.shtml');expect(screen.getAllByRole('link',{name:/第[12456]页/}).length).toBeGreaterThan(6)})
it('最新时钟在前，旧七家待办折叠且注明落款缺口已补',()=>{render(<STInitialWarningOrigin data={origin as InitialWarningOrigin} clock={clock as PenaltyClock}/>);expect(screen.getByRole('region',{name:'处罚时钟与实际摘帽'})).toBeVisible();expect(screen.getByRole('table',{name:'七家公司期初警示条件比较',hidden:true})).not.toBeVisible();fireEvent.click(screen.getByText('回看七家警示依据与当时待兑现条件'));expect(screen.getByText(/最终决定落款本轮已核/)).toBeVisible()})
