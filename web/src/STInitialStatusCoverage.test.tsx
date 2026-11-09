import {render,screen,fireEvent,within,cleanup} from '@testing-library/react'
import {describe,it,expect,afterEach} from 'vitest'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import fixture from './__fixtures__/initial-status-coverage.json'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
afterEach(cleanup)
describe('期初状态阅读覆盖',()=>{
 it('先解释约束，再展示相同窗口，不把覆盖当名单认证',()=>{render(<STInitialStatusCoverage data={fixture as InitialStatusCoverage}/>);expect(screen.getByRole('heading',{name:'同样是上涨异动，后面的风险和走势并不相同'})).toBeVisible();expect(screen.getByText(/由14家增至20家/)).toBeVisible();expect(screen.getByRole('region',{name:'六家期初成员同窗行情'})).toHaveTextContent('-21.13%');expect(screen.getByRole('region',{name:'六家期初成员同窗行情'})).toHaveTextContent('+27.34%');expect(screen.getByText(/不是随机样本/)).toBeVisible()})
 it('保留瑞和文件内部简称冲突及原因未核全的两家',()=>{render(<STInitialStatusCoverage data={fixture as InitialStatusCoverage}/>);fireEvent.click(screen.getByText('*ST瑞和：重整签约与财务警示并存'));expect(screen.getByText(/原件内部简称不一致/)).toBeVisible();fireEvent.click(screen.getByText('*ST南置：申请摘帽仍在补材料'));expect(within(screen.getByText('*ST南置：申请摘帽仍在补材料').closest('details')!).getByText('本件可证明当时仍受双重警示，但没有完整列明最初触发原因，原因原件另待补。')).toBeVisible()})
 it('完整150只缺记录仍保留，原件按具体页跳转',()=>{render(<STInitialStatusCoverage data={fixture as InitialStatusCoverage}/>);fireEvent.click(screen.getByText('核150只的阅读覆盖与剩余缺口'));expect(screen.getAllByText('仍缺')).toHaveLength(130);fireEvent.click(screen.getByText('*ST瑞和：重整签约与财务警示并存'));expect(within(screen.getByText('*ST瑞和：重整签约与财务警示并存').closest('details')!).getByRole('link',{name:/第4页/})).toHaveAttribute('target','_blank')})
})
