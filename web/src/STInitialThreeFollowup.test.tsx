import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STInitialThreeFollowup} from './STInitialThreeFollowup'
import type {InitialThreeFollowup} from './STInitialThreeFollowup'
import {STInitialStatusCoverage} from './STInitialStatusCoverage'
import type {InitialStatusCoverage} from './STInitialStatusCoverage'
import type {RuiheProcess} from './STRuiheProcess'
import data from './__fixtures__/initial-three-followup.json'
import initial from './__fixtures__/initial-status-coverage.json'
import ruihe from './__fixtures__/ruihe-process.json'
afterEach(cleanup)
it('新判断入口默认展示三家公司，切回瑞和和期初比较',()=>{render(<STInitialStatusCoverage data={initial as InitialStatusCoverage} ruihe={ruihe as RuiheProcess} three={data as InitialThreeFollowup}/>);expect(screen.getByLabelText('期初专题阅读目的')).toHaveValue('three');expect(screen.getByRole('table',{name:'三家公司原判断与更新'})).toBeVisible();expect(screen.queryByRole('region',{name:'瑞和重整程序与资金核对'})).toBeNull();fireEvent.change(screen.getByLabelText('期初专题阅读目的'),{target:{value:'ruihe'}});expect(screen.getByRole('region',{name:'瑞和重整程序与资金核对'})).toBeVisible();fireEvent.change(screen.getByLabelText('期初专题阅读目的'),{target:{value:'baseline'}});expect(screen.getByRole('region',{name:'六家期初成员同窗行情'})).toBeVisible()})
it('按公司解释股东会通过不等于法院和全款，原件按页可查',()=>{render(<STInitialThreeFollowup data={data as InitialThreeFollowup}/>);fireEvent.change(screen.getByLabelText('三家后续公司'),{target:{value:'002547'}});expect(screen.getByText(/不能继续写“尚待股东会”/)).toBeVisible();expect(screen.getByText(/累计4735.50万元是签订后10个工作日内应付/)).toBeVisible();fireEvent.click(screen.getByText('春兴：逐个节点与改变判断的下一份证据'));expect(screen.getAllByRole('link',{name:/原件第/}).some(a=>a.getAttribute('href')?.endsWith('#page=17'))).toBe(true)})
it('中岩撤回子公司申请和代偿后新债权不能合并为母公司风险全消',()=>{render(<STInitialThreeFollowup data={data as InitialThreeFollowup}/>);fireEvent.change(screen.getByLabelText('三家后续公司'),{target:{value:'002542'}});expect(screen.getByText(/子公司未进入清算程序/)).toBeVisible();expect(screen.getByText(/不是债务豁免或利润/)).toBeVisible()})
it('同期间财报保留亏损正现金与负权益，不由收入认证年度条件',()=>{render(<STInitialThreeFollowup data={data as InitialThreeFollowup}/>);fireEvent.click(screen.getByText('三家放在同一报表期间：利润、现金流与权益'));expect(screen.getByRole('table',{name:'三家同期间财务比较'})).toHaveTextContent('-11,001.74');expect(screen.getByRole('table',{name:'三家同期间财务比较'})).toHaveTextContent('2,654.89');expect(screen.getByText(/季报均未经审计/)).toBeVisible()})
it('同日双公告不重复验证，晚期5日与20日未满留空',()=>{render(<STInitialThreeFollowup data={data as InitialThreeFollowup}/>);fireEvent.click(screen.getByText('数源公告后：个股、ST与大盘同窗看'));expect(screen.getAllByText('同公司同日共享一次观察，不重复计验证')).toHaveLength(2);fireEvent.change(screen.getByLabelText('三家后续公司'),{target:{value:'002547'}});expect(screen.getByRole('table',{name:'三家后续同窗行情'})).toHaveTextContent('后窗未满');fireEvent.change(screen.getByLabelText('三家阶段观察窗口'),{target:{value:'20'}});expect(screen.getByRole('table',{name:'三家后续同窗行情'})).toHaveTextContent('未满或不可算')})
