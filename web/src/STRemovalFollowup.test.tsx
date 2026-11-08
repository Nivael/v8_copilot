import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,it,expect} from 'vitest'
import {STRemovalFollowup} from './STRemovalFollowup'
import fixture from './__fixtures__/jinglan-removal-followup.json'
afterEach(cleanup)
it('leads with the mixed outcome, then distinguishes cash receipts, profit and conditional execution',()=>{
 render(<STRemovalFollowup data={fixture}/>)
 expect(screen.getByText(/不能把摘帽、收齐一笔补偿/)).toBeVisible()
 expect(screen.getByText(/京蓝摘帽前20个市场日为/)).toBeVisible()
 expect(screen.getByText(/后20个市场日为-22.88%/)).toBeVisible()
 fireEvent.click(screen.getByText('先看摘帽依据，再核盈利、现金与履约'))
 expect(screen.getByText(/不能拿集团前三季扣非值判断全年达标/)).toBeVisible()
 expect(screen.getByText(/不是全额现金，也不是已收到/)).toBeVisible()
 expect(screen.getByText(/测算损失不是已确认损失/)).toBeVisible()
 fireEvent.click(screen.getByText('查看逐项公告与物理页码'))
 expect(screen.getByRole('link',{name:/第2页/})).toHaveAttribute('href',fixture.facts[0].source.url)
})
it('keeps pre-halt and resume-close dates separate, retains short windows and insufficient outcomes',()=>{
 render(<STRemovalFollowup data={fixture}/>)
 fireEvent.click(screen.getByText('核摘帽前后同窗、退出后的价格与报价覆盖'))
 expect(screen.getByText(/共19个个股成交日/)).toBeVisible();expect(screen.getByText(/原固定样本已经保留京蓝摘帽后的44个成交日/)).toBeVisible()
 expect(screen.getByText('2026-08-27 → 2026-09-24')).toBeVisible()
 expect(screen.getAllByText('后续交易日不足，保留空值。')).toHaveLength(2)
 fireEvent.change(screen.getByRole('combobox'),{target:{value:'1'}})
 expect(screen.getByText(/2026-11-04 → 2026-11-05/)).toBeVisible()
 expect(screen.getByText(/跨渠道核验尚缺/)).toBeVisible()
})
it('does not invent a removal followup for old snapshots',()=>{const {container}=render(<STRemovalFollowup data={null}/>);expect(container).toBeEmptyDOMElement()})
