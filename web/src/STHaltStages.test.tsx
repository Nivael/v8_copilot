import {render,screen,fireEvent} from '@testing-library/react'
import {describe,it,expect,vi} from 'vitest'
import {STHaltStages} from './STHaltStages'
import type {RegimeHaltStages} from './stRegimeTypes'
const data:RegimeHaltStages={through:'2026-11-06',new_primary_documents:2,new_primary_pages:4,reused_primary_documents:3,reused_primary_pages:13,boundary:'事先告知与最终决定分开。',rows:[{symbol:'002717',name:'岭南',halt_on:'2026-10-13',resume_on:null,answer:'已核至事先告知，最终决定未纳入证据。',what_changed:'新增交易类程序。',what_would_change:'正式最终文件。',halt_market_days:19,halt_dates:[],all_halt_days_confirmed:true,last_pre_halt_trade:{date:'2026-10-12',close:.45},resume_has_trade:null,facts:[{published_on:'2026-10-17',text:'10月16日收到事先告知',source:{announcement_id:'a',title:'正式公告',page:1,url:'https://example.test',sha256:'abc'}}]}]}
describe('halt stages',()=>{
 it('shows answer first and preserves open-ended stage while exposing evidence lazily',()=>{const onCompany=vi.fn();render(<STHaltStages data={data} onCompany={onCompany}/>);expect(screen.getByText(/最终决定未纳入证据/)).toBeVisible();expect(screen.getByText(/10月16日收到/)).not.toBeVisible();fireEvent.click(screen.getByText('核日期、原件与成交状态'));expect(screen.getByText(/10月16日收到/)).toBeVisible();expect(screen.getByText(/本轮核到2026-11-06/)).toBeVisible();fireEvent.click(screen.getByRole('button',{name:'看岭南公告与同窗行情 →'}));expect(onCompany).toHaveBeenCalledWith('002717')})
 it('does not invent evidence for old data',()=>{const {container}=render(<STHaltStages data={null} onCompany={()=>{}}/>);expect(container).toBeEmptyDOMElement()})
})
