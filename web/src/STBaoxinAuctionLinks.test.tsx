import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STBaoxinAuctionLinks} from './STBaoxinAuctionLinks'
import type {BaoxinAuctionLinks} from './STBaoxinAuctionLinks'
import raw from './__fixtures__/baoxin-auction-links.json'
const data=raw as unknown as BaoxinAuctionLinks
afterEach(cleanup)
it('先答三笔已配对登记，明确是股东股份不是上市公司融资',()=>{render(<STBaoxinAuctionLinks data={data}/>);expect(screen.getByRole('heading',{name:'后来过户的，到底是哪一笔竞拍？'})).toBeVisible();expect(screen.getByText('所核原件已明确配上3笔、合计1,342万股。')).toBeVisible();expect(screen.getByText(/江苏立青所持股份.*不等于上市公司收到融资款/)).toBeVisible();expect(screen.getByText(/拍卖截止 2026-08-29/)).toBeVisible()})
it('重拍两类型和竞买号保留，不累计2200万',()=>{render(<STBaoxinAuctionLinks data={data}/>);fireEvent.change(screen.getByLabelText('宝馨股份范围'),{target:{value:'reauction'}});fireEvent.click(screen.getAllByText('核本组依据 →')[0]);expect(screen.getByText(/竞买号 E4057/)).toBeVisible();expect(screen.getByText(/竞买号 P9195/)).toBeVisible();expect(screen.getByText(/仍是这1,100万股，不能重复累计为2200万股/)).toBeVisible()})
it('未配凭据不是断言未过户，942万不当11次验证',()=>{render(<STBaoxinAuctionLinks data={data}/>);fireEvent.change(screen.getByLabelText('宝馨股份范围'),{target:{value:'other'}});expect(screen.getByText(/不等于一定未过户或失败/)).toBeVisible();fireEvent.click(screen.getAllByText('核本组依据 →')[6]);expect(screen.getByText(/11位买受人分配合计942万股/)).toBeVisible()})
it('七月算术与日期冲突可追溯，不自行修复',()=>{render(<STBaoxinAuctionLinks data={data}/>);fireEvent.click(screen.getByText('七月的数字和日期冲突，怎样保留？'));expect(screen.getByText(/只减少900万股，相差200万股/)).toBeVisible();expect(screen.getByText(/最早公开时点仍未核/)).toBeVisible()})
it('同披露记录只观察一次，日期敏感性两窗口并列',()=>{render(<STBaoxinAuctionLinks data={data}/>);fireEvent.click(screen.getByText('公告后股价、大盘与ST怎样一起看？'));fireEvent.change(screen.getByLabelText('宝馨公告观察记录'),{target:{value:'second_fail_july'}});expect(screen.getByText(/按另一披露日2026-07-06/)).toBeVisible();fireEvent.change(screen.getByLabelText('宝馨公告观察记录'),{target:{value:'ownership_nov'}});fireEvent.change(screen.getByLabelText('宝馨公告观察窗口'),{target:{value:'20'}});expect(screen.getByText(/未满窗口.*不可算/)).toBeVisible()})
it('旧数据不显示新配对',()=>{const {container}=render(<STBaoxinAuctionLinks/>);expect(container).toBeEmptyDOMElement()})
it('依据收起后，同一行按钮仍能重新打开',()=>{render(<STBaoxinAuctionLinks data={data}/>);fireEvent.click(screen.getAllByText('核本组依据 →')[0]);const note=()=>screen.getByText(/11月4日原件明确回指8月28日2026-071号公告/);expect(note()).toBeVisible();fireEvent.click(screen.getByText('330万股：按日期与竞买号核对'));expect(note()).not.toBeVisible();fireEvent.click(screen.getAllByText('核本组依据 →')[0]);expect(note()).toBeVisible()})
