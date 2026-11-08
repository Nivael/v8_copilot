import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {describe,it,expect,vi,afterEach} from 'vitest'
import {STHaltStages} from './STHaltStages'
import type {RegimeHaltStages} from './stRegimeTypes'
const data:RegimeHaltStages={through:'2026-11-06',new_primary_documents:2,new_primary_pages:4,reused_primary_documents:3,reused_primary_pages:13,boundary:'事先告知与最终决定分开。',rows:[{symbol:'002717',name:'岭南',halt_on:'2026-10-13',resume_on:null,answer:'已核至事先告知，最终决定未纳入证据。',what_changed:'新增交易类程序。',what_would_change:'正式最终文件。',halt_market_days:19,halt_dates:[],all_halt_days_confirmed:true,last_pre_halt_trade:{date:'2026-10-12',close:.45},resume_has_trade:null,facts:[{published_on:'2026-10-17',text:'10月16日收到事先告知',source:{announcement_id:'a',title:'正式公告',page:1,url:'https://example.test',sha256:'abc'}}]}]}
afterEach(cleanup)
describe('halt stages',()=>{
 it('shows answer first and preserves open-ended stage while exposing evidence lazily',()=>{const onCompany=vi.fn();render(<STHaltStages data={data} onCompany={onCompany}/>);expect(screen.getByText(/最终决定未纳入证据/)).toBeVisible();expect(screen.getByText(/10月16日收到/)).not.toBeVisible();fireEvent.click(screen.getByText('核日期、原件与成交状态'));expect(screen.getByText(/10月16日收到/)).toBeVisible();expect(screen.getByText(/本轮核到2026-11-06/)).toBeVisible();fireEvent.click(screen.getByRole('button',{name:'看岭南公告与同窗行情 →'}));expect(onCompany).toHaveBeenCalledWith('002717')})
 it('does not invent evidence for old data',()=>{const {container}=render(<STHaltStages data={null} onCompany={()=>{}}/>);expect(container).toBeEmptyDOMElement()})
})

it('shows bounded title review without claiming absence of a final decision',()=>{
 const x:RegimeHaltStages={...data,rows:[{...data.rows[0],directory_review:{start:'2026-10-17',through:'2026-11-06',record_count:1,reported_total:1,terminal_has_more:false,source_sha256:'hash',query_url:'https://example.test/query',observed_at:'2026-11-09',rows:[{id:'x',title:'收到事先告知',published_on:'2026-10-17',url:'https://example.test/x'}],matched_final_titles:[],scope:'仅核标题，未读其他正文'}}]}
 render(<STHaltStages data={x} onCompany={()=>{}}/>);expect(screen.getByText(/不等于最终文件不存在/)).toBeVisible();expect(screen.getByText('仅核标题，未读其他正文')).not.toBeVisible();fireEvent.click(screen.getByText('看目录范围与逐条标题'));expect(screen.getByText('仅核标题，未读其他正文')).toBeVisible();expect(screen.getByRole('link',{name:/收到事先告知/})).toHaveAttribute('href','https://example.test/x')
})
