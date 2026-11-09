import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STRuiheProcess} from './STRuiheProcess'
import type {RuiheProcess} from './STRuiheProcess'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
import type {WarningBasisFollowup} from './STWarningBasisFollowup'
import data from './__fixtures__/ruihe-process.json'
import initial from './__fixtures__/initial-status-coverage.json'
import update from './__fixtures__/warning-basis-followup.json'
afterEach(cleanup)
it('默认按阅读目的只展示瑞和，切换后旧判断和六家比较仍可查看',()=>{render(<STInitialStatusCoverage data={initial as InitialStatusCoverage} update={update as WarningBasisFollowup} ruihe={data as RuiheProcess}/>);expect(screen.getByLabelText('期初专题阅读目的')).toHaveValue('ruihe');expect(screen.getByRole('region',{name:'瑞和重整程序与资金核对'})).toBeVisible();expect(screen.queryByRole('region',{name:'南置与西王判断更新'})).toBeNull();expect(screen.queryByRole('region',{name:'六家期初成员同窗行情'})).toBeNull();fireEvent.change(screen.getByLabelText('期初专题阅读目的'),{target:{value:'updates'}});expect(screen.getByRole('region',{name:'南置与西王判断更新'})).toBeVisible();expect(screen.queryByRole('region',{name:'瑞和重整程序与资金核对'})).toBeNull();fireEvent.change(screen.getByLabelText('期初专题阅读目的'),{target:{value:'baseline'}});expect(screen.getByRole('region',{name:'六家期初成员同窗行情'})).toBeVisible()})
it('计划总额、保证金、触发条件和过户后锁定分开表达',()=>{render(<STRuiheProcess data={data as RuiheProcess}/>);expect(screen.getByRole('heading',{name:'5000万保证金有披露，60个月仍是过户后的承诺'})).toBeVisible();expect(screen.getByText(/同窗5日看价格：5月签约披露后/)).toHaveTextContent('个股-22.61%，大盘-0.03%、ST参考-2.97%');expect(screen.getByText(/同窗5日看价格：5月签约披露后/)).toHaveTextContent('个股+22.56%，同期大盘+3.29%、ST参考+4.32%');fireEvent.click(screen.getByText('18.732亿元计划、5000万元保证金和付款时钟，怎样分开？'));expect(screen.getByText(/预计总对价为18.732亿元/)).toBeVisible();expect(screen.getByText(/从收到管理人书面付款通知起10个工作日/)).toBeVisible();expect(screen.getByText(/财务平台150万元、其他五组各500万元保证金/)).toBeVisible();expect(screen.getByText(/本轮没有拿到银行回单/)).toBeVisible()})
it('公安口头核实与证监会事项保留不同证据层次',()=>{render(<STRuiheProcess data={data as RuiheProcess}/>);fireEvent.click(screen.getByText('同样叫“立案”，瑞和、数源和西王是一回事吗？'));expect(screen.getByRole('table',{name:'三家公司立案机关比较'})).toHaveTextContent('*ST瑞和 · 公安机关');expect(screen.getByRole('table',{name:'三家公司立案机关比较'})).toHaveTextContent('当时未收到公安书面告知或通知');expect(screen.getByRole('table',{name:'三家公司立案机关比较'})).toHaveTextContent('*ST数源 · 中国证监会')})
it('窗口切换保留未满20日，不伪造零收益或同窗市场',()=>{render(<STRuiheProcess data={data as RuiheProcess}/>);fireEvent.click(screen.getByText('这些阶段之后，个股、ST与大盘怎样走？'));fireEvent.change(screen.getByLabelText('瑞和阶段观察窗口'),{target:{value:'20'}});expect(screen.getByRole('table',{name:'瑞和阶段同窗行情'})).toHaveTextContent('后窗未满');expect(screen.getByRole('table',{name:'瑞和阶段同窗行情'})).toHaveTextContent('未满或不可算')})
