import {afterEach,it,expect} from 'vitest'
import {render,screen,cleanup,fireEvent} from '@testing-library/react'
import {STPreRuleMembership} from './STPreRuleMembership'
import {STRemovalEraComparison} from './STRemovalEraComparison'
import {STPriceBandAudit} from './STPriceBandAudit'
import type {OfficialPDFAudit} from './STOfficialPDFAudit'
import type {RegimePreRuleMembership,RegimeRemovalEraComparison} from './stRegimeTypes'
import type {PriceBandAudit} from './STPriceBandAudit'
import auditFixture from './__fixtures__/official-pdf-audit.json'
import preFixture from './__fixtures__/pre-rule-membership.json'
import eraFixture from './__fixtures__/removal-era-comparison.json'
import bandFixture from './__fixtures__/price-band-audit.json'
const audit=auditFixture as OfficialPDFAudit
afterEach(cleanup)
it('制度前镜像现在有正式副本，原分类记录仍可查',()=>{
 render(<STPreRuleMembership data={preFixture as RegimePreRuleMembership} audit={audit}/>);expect(screen.getByRole('option',{name:'原镜像5处（正式副本已补）'})).toBeInTheDocument();fireEvent.change(screen.getByLabelText('制度前边界公司'),{target:{value:'603813'}});fireEvent.click(screen.getByText('看所引原页、日期差异与认证限制'));expect(screen.getByText(/本份原镜像现已取得巨潮正式副本/)).toBeVisible();expect(screen.getByRole('link',{name:'本轮已核巨潮正式PDF · 第1页 ↗'})).toHaveAttribute('href',audit.rows.find(r=>r.symbol==='603813')!.official_url+'#page=1')
})
it('旧官方来源子集明确为历史口径，不再声称当前镜像未核',()=>{
 render(<STRemovalEraComparison data={eraFixture as RegimeRemovalEraComparison} audit={audit}/>);expect(screen.getByRole('option',{name:'旧口径：当时直接官方PDF'})).toBeInTheDocument();fireEvent.change(screen.getByLabelText('制度前后摘帽范围'),{target:{value:'official_only'}});expect(screen.getByText(/历史来源子集，未纳入后来取得的正式副本/)).toBeVisible();fireEvent.change(screen.getByLabelText('制度前后摘帽公司'),{target:{value:'603813'}});fireEvent.click(screen.getByText('看该公司端点、公司行动和公告'));expect(screen.getByText(/原镜像已取得同字节巨潮正式副本/)).toBeVisible()
})
it('价格边界的天择分派原件同步显示官方副本',()=>{
 render(<STPriceBandAudit data={bandFixture as PriceBandAudit} audit={audit}/>);fireEvent.click(screen.getByText('用具体案例理解：取整、除权参考价与摘帽'));fireEvent.change(screen.getByLabelText('价格边界案例类型'),{target:{value:'reference'}});expect(screen.getByRole('link',{name:'巨潮正式副本已核，与原镜像字节相同 ↗'})).toHaveAttribute('href',audit.rows.find(r=>r.official_id==='1225312843')!.official_url);expect(screen.queryByText('发行人PDF镜像；官方原字节待补')).not.toBeInTheDocument()
})
