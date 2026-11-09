import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STDisclosureChains} from './STDisclosureChains'
import type {DisclosureChains} from './STDisclosureChains'
import raw from './__fixtures__/disclosure-chains.json'
const data=raw as unknown as DisclosureChains
afterEach(cleanup)
it('威领同日两项事实，只有一次行情观察',()=>{render(<STDisclosureChains data={data}/>);expect(screen.getByRole('heading',{name:'公告多了，事情真的向前走了吗？'})).toBeVisible();expect(screen.getByRole('heading',{name:'达到最低条件，结果与复牌确认'})).toBeVisible();expect(screen.getByRole('heading',{name:'资金结算和股份过户完成'})).toBeVisible();expect(screen.getAllByLabelText('2026-10-12一次同窗观察')).toHaveLength(1);expect(screen.getByText(/控制认定生效日 2026-11-04；披露日仍为 2026-11-06/)).toBeVisible()})
it('龙元办理安排与完成证明分开，期满日不是结果披露日',()=>{render(<STDisclosureChains data={data}/>);fireEvent.change(screen.getByLabelText('选择公告链'),{target:{value:'600491'}});expect(screen.getByText(/要约期满日 2026-08-26；披露日仍为 2026-08-28/)).toBeVisible();expect(screen.getByRole('heading',{name:'新原件确认清算过户完成'})).toBeVisible();fireEvent.click(screen.getAllByText('核对本项事实与原文')[3]);expect(screen.getByText('本次要约收购清算过户手续将于近日办理。',{exact:false})).toBeVisible();expect(screen.getAllByRole('link').some(a=>a.getAttribute('href')?.includes('#page=1#'))).toBe(false)})
it('沐邦两次流拍，不当成资产变现或股东股份',()=>{render(<STDisclosureChains data={data}/>);fireEvent.change(screen.getByLabelText('选择公告链'),{target:{value:'603398'}});expect(screen.getByText(/都不能当成已变现收入，也不是控股股东股份过户/)).toBeVisible();expect(screen.getByText(/一拍截止日 2026-10-09；披露日仍为 2026-10-17/)).toBeVisible();expect(screen.getByText(/二拍截止日 2026-11-03；披露日仍为 2026-11-04/)).toBeVisible()})
it('停牌起点和未满窗不补零',()=>{render(<STDisclosureChains data={data}/>);expect(screen.getAllByText(/起止含停牌或缺实际成交/).length).toBeGreaterThan(0);fireEvent.change(screen.getByLabelText('公告链行情窗口'),{target:{value:'20'}});expect(screen.getAllByText(/后窗未满，不填零、不缩窗/).length).toBeGreaterThan(0)})
it('统计只覆盖选定三链，不认证全部公告去重',()=>{render(<STDisclosureChains data={data}/>);fireEvent.click(screen.getByText('哪些是重复观察，哪些是真正的阶段更新？'));expect(screen.getByText(/13份已冻结旧文件、12项原事实、11个同公司披露日/)).toBeVisible();expect(screen.getByText(/没有宣称完成全库跨文件去重/)).toBeVisible()})
it('没有来源绑定时不展示关系认证',()=>{const {container}=render(<STDisclosureChains/>);expect(container).toBeEmptyDOMElement()})
