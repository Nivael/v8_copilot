import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STRemovalEraComparison} from './STRemovalEraComparison'
import type {RegimeRemovalEraComparison} from './stRegimeTypes'
import raw from './__fixtures__/removal-era-comparison.json'
const data=raw as RegimeRemovalEraComparison
afterEach(cleanup)
describe('制度前后摘帽比较',()=>{
 it('首日与后续分开，默认36/10不称制度净因果',()=>{render(<STRemovalEraComparison data={data}/>);expect(screen.getByRole('heading',{name:'摘帽以后，7月前后有什么不同？'})).toBeVisible();expect(screen.getByText(/制度前事件组36只可核、10涨26跌.*制度后组10只可核、5涨5跌/)).toBeVisible();expect(screen.getByText(/前组22个窗口跨过7月6日/)).toBeVisible();expect(screen.getByRole('img',{name:'制度前事件组：10涨、26跌、0平'})).toBeVisible()})
 it('纯前窗口14家，40日空组不填零',()=>{render(<STRemovalEraComparison data={data}/>);fireEvent.change(screen.getByLabelText('制度前后摘帽范围'),{target:{value:'pure_regime'}});expect(screen.getByRole('img',{name:'制度前事件组：5涨、9跌、0平'})).toBeVisible();fireEvent.change(screen.getByLabelText('制度前后摘帽窗口'),{target:{value:'40'}});expect(screen.getByText('没有符合此范围的完整可核窗口，不填零。')).toBeVisible();expect(screen.getByText(/前组没有完整落在旧制度的40日窗口/)).toBeVisible()})
 it('仅官方PDF敏感性减少分母而不升级镜像',()=>{render(<STRemovalEraComparison data={data}/>);fireEvent.change(screen.getByLabelText('制度前后摘帽范围'),{target:{value:'official_only'}});expect(screen.getByRole('img',{name:'制度前事件组：9涨、22跌、0平'})).toBeVisible();fireEvent.change(screen.getByLabelText('制度前后摘帽公司'),{target:{value:'603813'}});fireEvent.click(screen.getByText('看该公司端点、公司行动和公告'));expect(screen.getByText(/发行人公告PDF镜像，官方原字节待补/)).toBeVisible()})
 it('保留未满窗口与华微因子差异，不借绝味解释',()=>{render(<STRemovalEraComparison data={data}/>);fireEvent.change(screen.getByLabelText('制度前后摘帽公司'),{target:{value:'600360'}});expect(screen.getByText(/公司行动与复权构造待核.*不进入主统计/)).toBeVisible();fireEvent.change(screen.getByLabelText('制度前后摘帽公司'),{target:{value:'603517'}});expect(screen.getByText(/后窗未满.*不进入主统计/)).toBeVisible();fireEvent.change(screen.getByLabelText('制度前后摘帽窗口'),{target:{value:'5'}});fireEvent.click(screen.getByText('看该公司端点、公司行动和公告'));expect(screen.getByText(/已有公告与公司行动构造重建/)).toBeVisible()})
 it('起点切换同时更换窗口，复牌首日市场含停牌',()=>{render(<STRemovalEraComparison data={data}/>);fireEvent.change(screen.getByLabelText('制度前后摘帽起点'),{target:{value:'including_resume'}});expect(screen.getByText(/从停牌前收盘起的20个市场交易日/)).toBeVisible();expect(screen.getByText(/大盘也按这两端同窗比较，包含停牌日/)).toBeVisible()})
 it('配对前史不足不缩窗，先涨后跌不双计',()=>{render(<STRemovalEraComparison data={data}/>);fireEvent.click(screen.getByText('哪些没有纳入，前后配对会少多少？'));expect(screen.getByText(/前组只剩22家，后组10家/)).toBeVisible();expect(screen.getByText(/前组25家复牌先涨中，18家.*不能算两次案例/)).toBeVisible()})
 it('旧6涨与新5涨来自不同起止，不把差额当首日贡献',()=>{render(<STRemovalEraComparison data={data}/>);fireEvent.click(screen.getByText('为什么与原12只的20日结果不同？'));expect(screen.getByText(/20日有6\/10只上涨.*为5\/10只上涨.*起点、终点都不同/)).toBeVisible();expect(screen.getByText(/宁科.*\+2.45%.*-6.74%.*方向会变/)).toBeVisible()})
 it('旧快照没有虚构比较',()=>{expect(render(<STRemovalEraComparison data={null}/>).container).toBeEmptyDOMElement()})
})
