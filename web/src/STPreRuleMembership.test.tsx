import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STPreRuleMembership} from './STPreRuleMembership'
import type {RegimePreRuleMembership} from './stRegimeTypes'
import raw from './__fixtures__/pre-rule-membership.json'
const data=raw as RegimePreRuleMembership
afterEach(cleanup)
describe('制度前成员移出边界',()=>{
 it('先区分37撤销、10整理、1摘牌及来源级别',()=>{render(<STPreRuleMembership data={data}/>);expect(screen.getByRole('heading',{name:'制度前移出的48只，究竟去了哪里？'})).toBeVisible();expect(screen.getByText(/37次撤销风险警示、10次进入退市整理、1次公告摘牌/)).toBeVisible();expect(screen.getByText(/43份来自官方文档，5份为发行人公告PDF镜像/)).toBeVisible();expect(screen.getByText(/不把48个边界说成197只期初名单/)).toBeVisible()})
 it('新规前后机制不混，原文未写的前值不补造',()=>{render(<STPreRuleMembership data={data}/>);expect(screen.getByText(/其中28份.*另9份只明示撤销后10%/)).toBeVisible();expect(screen.getByText(/此前核过的12次.*仍为10%/)).toBeVisible();expect(screen.getByText(/6月29日撤销.*11月4日再次ST/)).toBeVisible()})
 it('表格筛镜像只列5家，未当直接官方原件',()=>{render(<STPreRuleMembership data={data}/>);fireEvent.change(screen.getByLabelText('制度前边界范围'),{target:{value:'mirror'}});fireEvent.click(screen.getByText('展开逐公司日期与来源级别'));expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(6);expect(screen.getAllByText('交易所目录＋公告PDF镜像')).toHaveLength(5)})
 it('万方摘牌、国华整理与沪科日期差异可核',()=>{render(<STPreRuleMembership data={data}/>);fireEvent.change(screen.getByLabelText('制度前边界公司'),{target:{value:'000638'}});expect(screen.getByText(/不误写为退市整理起点/)).toBeVisible();fireEvent.change(screen.getByLabelText('制度前边界公司'),{target:{value:'000004'}});expect(screen.getByText(/不用它认证实际最后交易日或后续摘牌日/)).toBeVisible();fireEvent.change(screen.getByLabelText('制度前边界公司'),{target:{value:'600608'}});fireEvent.click(screen.getByText('看所引原页、日期差异与认证限制'));expect(screen.getByText(/2026-06-07.*2026-06-08.*先后存在差异/)).toBeVisible()})
 it('原尚镜像来源保持标记和原目录链接',()=>{render(<STPreRuleMembership data={data}/>);fireEvent.change(screen.getByLabelText('制度前边界公司'),{target:{value:'603813'}});fireEvent.click(screen.getByText('看所引原页、日期差异与认证限制'));expect(screen.getByText(/官方原PDF字节尚未取得/)).toBeVisible();expect(screen.getByRole('link',{name:'交易所目录原公告链接 ↗'})).toHaveAttribute('href',data.rows.find(r=>r.symbol==='603813')!.source.catalog_url)})
 it('旧快照不虚构验证',()=>{expect(render(<STPreRuleMembership data={null}/>).container).toBeEmptyDOMElement()})
})
