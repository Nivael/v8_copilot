import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {ETFRegistrationRules} from './ETFRegistrationRules'
import type {ETFRegistrationRules as Rules} from './types'

const doc=(label:string,published_on:string,effective_on:string,pages:number[],clause_count:number)=>({label,title:label+' 登记规则',published_on,effective_on,
  url:`https://www.chinaclear.cn/${label}.pdf`,response_url:`https://www.chinaclear.cn/${label}.pdf`,observed_at:'2026-11-05T12:28:20Z',raw_sha256:label+'-original',text_sha256:label+'-text',bytes:1000,pages:label==='sh-guide'?36:label==='sz-guide'?78:20,proof_pages:pages,clause_count,effective_proof_page:pages.at(-1)!})
const base:Rules={version:'etf_registration_scoped_rules_v1',availability:'scoped_rules_reviewed',reviewed_versions:3,reviewed_clauses:12,source_pages:134,identity_and_proof_pages:14,
  content_digest:'rules-proof',materialized_at:'2026-11-05T12:30:00Z',index:{url:'https://www.chinaclear.cn/index',response_url:'https://www.chinaclear.cn/index',sha256:'index-proof',observed_at:'2026-11-05T12:27:00Z'},
  documents:[doc('sh-guide','2026-05-22','2026-05-25',[1,17,27],2),doc('sz-guide','2026-08-07','2026-08-10',[1,11,33,38,59],4),doc('central-exchange','2026-09-11','2026-09-11',[1,3,8,9,18,19],6)],
  daily_registration_data_acquired:false,full_document_semantics_checked:false,full_window_versions_checked:false,whole_fund_daily_scope_verified:false,share_precision_verified:false,final_revision_verified:false,corporate_actions_checked:false,historical_PIT:false,effect_measured:false,estimated_net_subscription_yuan:null,
  note:'指定条款不是实际日登记数据、全基金范围或资金身份。'}

describe('ETFRegistrationRules',()=>{
  afterEach(cleanup)
  const open=()=>fireEvent.click(screen.getByText('登记机构的规则说明了哪些数据'))
  it('starts collapsed and separates three institutional documents and scoped clauses from acquired daily data',()=>{
    render(<ETFRegistrationRules data={base}/>);
    expect(screen.getByText('登记机构的规则说明了哪些数据').closest('details')).not.toHaveAttribute('open')
    open();expect(screen.getByText(/3份2026版文件、12处指定条款.*134.*没有取得这些通道的实际日登记数据/)).toBeVisible()
    expect(screen.getByText(/不能倒用到更早日期/)).toBeVisible()
    expect(screen.getByText(/净申赎金额继续未发布/)).toBeVisible()
  })
  it('keeps exchange-only holders, direct subscription route and incremental backups distinct',()=>{
    render(<ETFRegistrationRules data={base}/>);open()
    expect(screen.getByText(/全体场内持有人名册/)).toBeVisible()
    expect(screen.getByText(/不是场外份额类别或实际投资者身份的证明/)).toBeVisible()
    expect(screen.getByText(/不适用于ETF等产品的交易所场内份额业务.*每日备份是增量/)).toBeVisible()
    expect(screen.getByText(/T\+1日21:00.*不是交易所ETF日份额最终修订确认/)).toBeVisible()
  })
  it('links actual physical pages and keeps listed publication separate from effective date',()=>{
    render(<ETFRegistrationRules data={base}/>);open()
    const rows=screen.getAllByRole('row')
    expect(within(rows[1]).getByText(/发布 2026-05-22/)).toBeVisible()
    expect(within(rows[2]).getByText(/施行 2026-08-10/)).toBeVisible()
    expect(screen.getByRole('link',{name:'名册范围 · 第17页 ↗'})).toHaveAttribute('href',base.documents[0].url+'#page=17')
    expect(screen.getByRole('link',{name:'每日明细 · 第33页 ↗'})).toHaveAttribute('href',base.documents[1].url+'#page=33')
    expect(screen.getByRole('link',{name:'适用排除 · 第18页 ↗'})).toHaveAttribute('href',base.documents[2].url+'#page=18')
    fireEvent.click(screen.getByText('查看全部指定证明页与取得时间'))
    expect(screen.getAllByRole('link',{name:/第\d+物理页/})).toHaveLength(14)
    expect(screen.getByText('sh-guide-original')).toBeVisible()
  })
  it.each([{...base,availability:'invalid'}, {...base,reviewed_clauses:null}, {...base,version:'other'}, {...base,documents:[base.documents[0],base.documents[0],base.documents[2]]}])('withholds old details when source verification or identity is incomplete',data=>{
    render(<ETFRegistrationRules data={data}/>);open()
    expect(screen.getByText(/不沿用上次的具体范围、时点或版本数量/)).toBeVisible()
    expect(screen.queryByRole('table')).not.toBeInTheDocument();expect(screen.queryByText(/GLRMX/)).not.toBeInTheDocument()
  })
  it('uses the source effective dates in the scope warning rather than a fixed string',()=>{
    render(<ETFRegistrationRules data={{...base,documents:[base.documents[0],{...base.documents[1],effective_on:'2026-08-11'},base.documents[2]]}}/>);open()
    expect(screen.getByText(/分别为 2026-08-11、2026-09-11/)).toBeVisible()
  })
  it('supports bounded keyboard scrolling while retaining native link keys and browser shortcuts',()=>{
    render(<ETFRegistrationRules data={base}/>);open()
    const region=screen.getByRole('region',{name:'可滚动的登记机构规则范围表'});region.scrollBy=vi.fn()
    expect(fireEvent.keyDown(region,{key:'ArrowRight'})).toBe(false);expect(region.scrollBy).toHaveBeenLastCalledWith({left:40,top:0,behavior:'auto'})
    expect(fireEvent.keyDown(region,{key:'PageDown'})).toBe(false);expect(region.scrollBy).toHaveBeenLastCalledWith({left:0,top:40,behavior:'auto'})
    vi.mocked(region.scrollBy).mockClear()
    expect(fireEvent.keyDown(screen.getByRole('link',{name:'名册范围 · 第17页 ↗'}),{key:'ArrowLeft'})).toBe(true)
    expect(fireEvent.keyDown(region,{key:'ArrowLeft',altKey:true})).toBe(true);expect(region.scrollBy).not.toHaveBeenCalled()
  })
})
