import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STRemovalEraComparison} from './STRemovalEraComparison'
import type {RegimeRemovalEraComparison} from './stRegimeTypes'
import raw from './__fixtures__/removal-action-basis.json'
const data=raw as RegimeRemovalEraComparison
afterEach(cleanup)
const open=()=>fireEvent.click(screen.getByText('为什么能补回？核四份公告、两种构造与旧结论'))
describe('公司行动补回与判断更新',()=>{
 it('默认37中11涨26跌，40日均值负转正但中位仍负',()=>{render(<STRemovalEraComparison data={data}/>);expect(screen.getByText(/前组20日由36只变37只.*11涨26跌.*40日简单均值由-1.72%变\+4.08%.*中位数仍为-7.66%/)).toBeVisible();expect(screen.getByRole('img',{name:'制度前事件组：11涨、26跌、0平'})).toBeVisible()})
 it('四公告二镜像，未来公告不倒填当时已知',()=>{render(<STRemovalEraComparison data={data}/>);open();expect(screen.getByText(/4份11页公告：2份直接官方PDF、2份发行人PDF镜像/)).toBeVisible();expect(screen.getByText(/10月公告只用于11月6日截止的回看构造，不能倒填/)).toBeVisible();expect(screen.getByRole('heading',{name:'2026-06-08除息：每股0.021元'})).toBeVisible();expect(screen.getByRole('heading',{name:'2026-10-27除息：每股0.043元'})).toBeVisible()})
 it('艾艾40日虽重建，仍在严格官方来源组外',()=>{render(<STRemovalEraComparison data={data}/>);fireEvent.change(screen.getByLabelText('制度前后摘帽窗口'),{target:{value:'40'}});fireEvent.change(screen.getByLabelText('制度前后摘帽范围'),{target:{value:'official_only'}});expect(screen.getByRole('img',{name:'制度前事件组：13涨、18跌、0平'})).toBeVisible();fireEvent.click(screen.getByText('看该公司端点、公司行动和公告'));expect(screen.getByText(/所用行动证明包含发行人PDF镜像.*不进入仅官方来源分布/)).toBeVisible()})
 it('华微20日补入，支持来自本窗口官方六月行动',()=>{render(<STRemovalEraComparison data={data}/>);fireEvent.change(screen.getByLabelText('制度前后摘帽公司'),{target:{value:'600360'}});fireEvent.click(screen.getByText('看该公司端点、公司行动和公告'));expect(screen.getByText(/本窗口新增本公司行动支持：1225342323.*直接官方PDF/)).toBeVisible();expect(screen.getByText(/本公司分派原文与同因子构造重建/)).toBeVisible()})
 it('荣丰总额推算与现金单位分开，日期第2页可核',()=>{render(<STRemovalEraComparison data={data}/>);open();fireEvent.change(screen.getByLabelText('摘帽公司行动核验公司'),{target:{value:'000668'}});expect(screen.getByRole('heading',{name:'2026-07-08除息：每股0.16元'})).toBeVisible();expect(screen.getByText(/本轮推算总额23494702.40元，不冒充公告明确列出的总额/)).toBeVisible();expect(screen.getByRole('link',{name:'登记/除息日期 · 第2页 ↗'})).toHaveAttribute('href',expect.stringContaining('#page=2'))})
 it('后窗不足和停牌不被构造重建掩盖',()=>{render(<STRemovalEraComparison data={data}/>);fireEvent.change(screen.getByLabelText('制度前后摘帽窗口'),{target:{value:'5'}});expect(screen.getByText(/端点无实际成交，不进入主统计/)).toBeVisible();fireEvent.change(screen.getByLabelText('制度前后摘帽窗口'),{target:{value:'20'}});fireEvent.change(screen.getByLabelText('制度前后摘帽公司'),{target:{value:'603517'}});expect(screen.getByText(/后窗未满，不进入主统计/)).toBeVisible()})
})
