import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {STMemberTransitions} from './STMemberTransitions'
import type {RegimeMemberTransitions} from './stRegimeTypes'
const source={url:'https://example.com/primary.pdf#page=1',sha256:'a'.repeat(64),page:1,title:'原公告'}
const row={symbol:'000711',anchor_name:'ST京蓝',new_name:'京蓝科技',status:'warning_removed',warning_removed:'other',announced_on:'2026-08-28',suspend_on:'2026-08-28',effective_on:'2026-08-31',provider_last_st:'2026-08-28',provider_first_absent:'2026-08-31',effective_matches_membership:true,facts:[{published_on:'2026-08-28',occurred_on:null,text:'已获同意，8月31日生效；索赔仍需另核。',source}]}
const data:RegimeMemberTransitions={anchor:'2026-07-03',through:'2026-11-06',total:2,counts:{warning_removed:1,delisting_period:1},matching_boundaries:2,boundary:'只核所列边界，新增原因待核。',rows:[row,{...row,symbol:'002731',anchor_name:'ST萃华',new_name:'萃华退',status:'delisting_period',warning_removed:null,announced_on:'2026-10-16',effective_on:'2026-10-23'}]}
afterEach(cleanup)
describe('名单移出路径',()=>{
 it('公告日与生效日分列，支持按退出路径查看并展开原件',()=>{
  render(<STMemberTransitions data={data}/>)
  expect(screen.getByText('ST京蓝')).toBeVisible()
  fireEvent.change(screen.getByLabelText('移出ST名单路径'),{target:{value:'delisting_period'}})
  expect(screen.queryByText('ST京蓝')).not.toBeInTheDocument()
  expect(screen.getByText('ST萃华')).toBeVisible()
  fireEvent.click(screen.getByText('看原公告与边界'))
  expect(screen.getByRole('link',{name:'原公告 · 第1页 ↗'})).toHaveAttribute('href',source.url)
 })
 it('缺少核实资料时不猜移出原因',()=>{
  render(<STMemberTransitions data={null}/>)
  expect(screen.queryByRole('region',{name:'ST名单移出原因'})).not.toBeInTheDocument()
 })
 it('摘牌状态不伪造新的证券简称',()=>{
  const d={...data,total:1,counts:{voluntary_delisted:1},matching_boundaries:1,rows:[{...row,symbol:'000016',anchor_name:'*ST康佳A',new_name:null,status:'voluntary_delisted',warning_removed:null}]}
  render(<STMemberTransitions data={d}/>)
  expect(screen.getByText('000016 · 原交易所已摘牌')).toBeVisible()
  expect(screen.queryByText(/→ 退市后股份/)).not.toBeInTheDocument()
 })

})
