import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,it} from 'vitest'
import {STMemberEntries} from './STMemberEntries'
import type {RegimeMemberEntries} from './stRegimeTypes'
const source={sha256:'a'.repeat(64),page:6,title:'重整原件',url:'https://example.com/primary.pdf#page=6'}
const missing={through:null,market_days:null,stock_pct:null,market_pct:null,st_pct:null,gap:'窗口未满，未填零'}
const data:RegimeMemberEntries={anchor:'2026-07-03',through:'2026-11-06',total:1,matching_boundaries:1,composition:{initial:150,entered:6,left:14,endpoint:142},boundary:'不分摊因果贡献',rows:[{symbol:'000972',previous_name:'中基健康',new_name:'*ST中基',warning_type:'delisting',cause:'法院正式受理重整',cause_key:'reorganization_accepted',reason:'公司获正式受理，子公司另案。',boundary:'不是已执行完毕。',announced_on:'2026-11-03',suspend_on:'2026-11-03',effective_on:'2026-11-04',first_provider_st:'2026-11-04',effective_matches_membership:true,facts:[{text:'按协议足额支付至临时管理人账户。',published_on:'2026-11-03',occurred_on:null,source}],observation:{anchor:'2026-11-02',not_earliest_reaction:true,windows:{'5':missing,'20':missing,through:{through:'2026-11-06',market_days:4,stock_pct:3,market_pct:1,st_pct:-2,gap:null}}}}]}
afterEach(cleanup)
it('未满窗口不填零，切换到截至日后显示同一对日期及原件',()=>{
 render(<STMemberEntries data={data}/>);fireEvent.click(screen.getByText('看事实与同窗表现'))
 expect(screen.getAllByText('未计算')).toHaveLength(3)
 expect(screen.getByText('按协议足额支付至临时管理人账户。')).toBeVisible()
 fireEvent.change(screen.getByLabelText('新增ST同窗观察窗口'),{target:{value:'through'}})
 expect(screen.getByText('+3.00%')).toBeVisible()
 expect(screen.getByText(/2026-11-02 → 2026-11-06/)).toBeVisible()
 expect(screen.getByRole('link',{name:'重整原件 · 第6页 ↗'})).toHaveAttribute('href',source.url)
})
it('缺资料时不虚构新增原因',()=>{
 render(<STMemberEntries data={null}/>);expect(screen.queryByRole('region',{name:'新增ST的原因与观察'})).not.toBeInTheDocument()
})
