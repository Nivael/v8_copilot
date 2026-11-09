import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STExperienceCaseAudit} from './STExperienceCaseAudit'
import type {ExperienceCaseAudit} from './STExperienceCaseAudit'
import raw from './__fixtures__/experience-case-audit.json'
const data=raw as unknown as ExperienceCaseAudit
afterEach(cleanup)
it('先答不能照用，再同时呈现首日上涨与未涨组',()=>{render(<STExperienceCaseAudit data={data}/>);expect(screen.getByRole('heading',{name:'摘帽首日上涨，能当成后续继续涨的经验吗？'})).toBeVisible();expect(screen.getByText('现在不能直接照用。')).toBeVisible();expect(screen.getByText(/制度前随后20日有 7 涨、18 跌；制度后有 3 涨、2 跌/)).toBeVisible();expect(screen.getByText('制度前37例 · 首日未涨')).toBeVisible()})
it('窗口不是新增案例，来源筛选重算',()=>{render(<STExperienceCaseAudit data={data}/>);fireEvent.change(screen.getByLabelText('经验检验窗口'),{target:{value:'40'}});expect(screen.getByText(/随后40日有 11 涨、14 跌/)).toBeVisible();fireEvent.change(screen.getByLabelText('经验检验来源范围'),{target:{value:'official_only'}});fireEvent.click(screen.getByText('有多少不同案例，哪些只是重复测量？'));expect(screen.getByText(/147 个后续窗口.*142 个可核.*49 个不同公司/)).toBeVisible();expect(screen.getByText(/603580：本次仅官方范围排除/)).toBeVisible()})
it('支持与反例使用同窗大盘和ST，未满窗不补零',()=>{render(<STExperienceCaseAudit data={data}/>);fireEvent.click(screen.getByText('看支持案例、反例与未完成项'));expect(screen.getByText(/随后20市场日：个股/)).toBeVisible();fireEvent.change(screen.getByLabelText('经验检验案例类别'),{target:{value:'support'}});expect(screen.getByText(/同窗大盘/)).toBeVisible();fireEvent.change(screen.getByLabelText('经验检验案例类别'),{target:{value:'unresolved'}});expect(screen.getByText(/后窗未满，不缩短窗口、不替换端点/)).toBeVisible()})
it('证据数量与验证数量分开，披露窗口共享市场',()=>{render(<STExperienceCaseAudit data={data}/>);fireEvent.click(screen.getByText('有多少不同案例，哪些只是重复测量？'));expect(screen.getByText(/204 份文件、198 条原记录、197 个阅读事项.*不是这条经验的验证次数/)).toBeVisible();expect(screen.getByText(/512\/666 对.*27\/45 对/)).toBeVisible();expect(screen.getByText(/002856.*2 条原记录、1 份来源文件/)).toBeVisible()})
it('列出改判条件，没有自动经验晋级',()=>{render(<STExperienceCaseAudit data={data}/>);fireEvent.click(screen.getByText('这轮保留什么，什么新证据会改变判断？'));expect(screen.getByText(/样本外对照反复支持稳定增益/)).toBeVisible();expect(screen.getByText(/经验库状态保持不变/)).toBeVisible()})
it('旧数据不授予新验证',()=>{const {container}=render(<STExperienceCaseAudit/>);expect(container).toBeEmptyDOMElement()})

it('首日未涨组也可查具体案例，绝味三文件只撑一例',()=>{render(<STExperienceCaseAudit data={data}/>);fireEvent.click(screen.getByText('看支持案例、反例与未完成项'));fireEvent.change(screen.getByLabelText('经验检验窗口'),{target:{value:'5'}});fireEvent.change(screen.getByLabelText('经验检验案例类别'),{target:{value:'comparison'}});fireEvent.change(screen.getByLabelText('经验检验公司'),{target:{value:data.rows.find(r=>r.symbol==='603517')!.case_id}});expect(screen.getAllByRole('link',{name:/本窗口公司行动证明/})).toHaveLength(3)})
