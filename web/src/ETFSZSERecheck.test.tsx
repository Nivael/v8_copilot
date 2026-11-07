import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {ETFSZSERecheck} from './ETFSZSERecheck'
import type {SZSERevisionRecheck} from './types'

const difference={overlap_observations:61,changed_observations:0,changes:[],new_dates:[],missing_previous_dates:[]}
const fixture:SZSERevisionRecheck={version:'szse_etf_revision_recheck_v1',availability:'observed',share_observations:183,share_changes:0,nav_observations:30,
  start:'2026-08-04',through:'2026-11-04',sessions:61,first_observed_at:'2026-11-05T01:35:28Z',last_observed_at:'2026-11-05T01:35:38Z',
  baseline_fetched_at:'2026-11-04T20:36:21Z',baseline_digest:'a'.repeat(64),transport:'HTTP',final_revision_verified:false,
  share_revision_status:'final_revision_unverified',corporate_actions_checked:false,estimated_net_subscription_yuan:null,note:'重读不是最终修订认证，净申赎金额继续未发布。',
  responses:[{code:'159919.SZ',kind:'shares',page:1,url:'http://fund.szse.cn/api/report/ShowReport/data?CATALOGID=fund_jjgm&txtDm=159919',observed_at:'2026-11-05T01:35:28Z',response_sha256:'b'.repeat(64)}],
  funds:[{code:'159919.SZ',latest_shares_ten_thousand:'1405911.66',share_observations:61,nav_observations:10,nav_through:'2026-11-03',share_comparison:difference,
    nav_comparison:{...difference,overlap_observations:10},issuer_nav_comparison:{overlap_observations:10,changed_observations:0,changes:[]}}]}

function open(){fireEvent.click(screen.getByText('查看三只ETF的复核差异与来源'))}

describe('ETFSZSERecheck',()=>{
  afterEach(cleanup)
  it('shows the later observation with separate NAV coverage and no final certification',()=>{
    render(<ETFSZSERecheck data={fixture}/>);open()
    expect(screen.getByText(/本次重读 183 条份额，较所绑定原快照变化 0 条/)).toBeVisible()
    expect(screen.getByText(/2026\/11\/5 09:35:28 至 2026\/11\/5 09:35:38/)).toBeVisible()
    expect(screen.getByText(/净值仅返回 30 条/)).toBeVisible()
    expect(screen.getByText('1,405,911.66 万份')).toBeVisible()
    expect(screen.getByText('10 条，截至 2026-11-03')).toBeVisible()
    expect(screen.getByText('无变化也不等于最终修订已认证')).toBeVisible()
    expect(screen.getByText('最终修订版仍待确认')).toBeVisible()
    expect(screen.getByText('与基金公司重叠 10 条，不一致 0 条')).toBeVisible()
  })
  it('preserves the actual HTTP query and original observation time for replayed evidence',()=>{
    render(<ETFSZSERecheck data={fixture}/>);open();fireEvent.click(screen.getByText('实际查询与归档绑定'))
    expect(screen.getByRole('link',{name:'159919.SZ · 份额 · 查询第1页 ↗'})).toHaveAttribute('href',fixture.responses?.[0].url)
    expect(screen.getByText(/实际请求为深交所官方 HTTP 接口/)).toBeVisible()
    expect(screen.getByText(/原快照取得 2026\/11\/5 04:36:21/)).toBeVisible()
    expect(screen.getByText('a'.repeat(64))).toBeVisible()
  })
  it('shows real changes and unavailable issuer overlaps without inventing agreement or cash flow',()=>{
    const fund=fixture.funds[0]
    render(<ETFSZSERecheck data={{...fixture,share_changes:1,funds:[{...fund,
      share_comparison:{...difference,changed_observations:1,changes:[{date:'2026-11-04',before:'1234.56',after:'1234.57',difference:'0.01'}]},
      nav_comparison:{...fund.nav_comparison,changed_observations:1,new_dates:['2026-11-03'],missing_previous_dates:['2026-10-20'],changes:[{date:'2026-11-02',before:'4.1234',after:'4.1235',difference:'0.0001'}]},
      issuer_nav_comparison:{overlap_observations:0,changed_observations:0,changes:[]}}]}}/>);open()
    expect(screen.getByText('2026-11-04：1,234.56 → 1,234.57 万份')).toBeVisible()
    expect(screen.getByText('原净值差异 2026-11-02：4.1234 → 4.1235 元')).toBeVisible()
    expect(screen.getByText('本次新增日期 1 个，原有日期未返回 1 个')).toBeVisible()
    expect(screen.getByText('基金公司净值未取得匹配日期，尚未交叉核对')).toBeVisible()
    expect(screen.queryByText('与基金公司重叠 10 条，不一致 0 条')).not.toBeInTheDocument()
    expect(screen.getByText('最终修订版仍待确认')).toBeVisible()
  })
  it('removes stale numbers and source links when the original snapshot changes',()=>{
    render(<ETFSZSERecheck data={{...fixture,availability:'baseline_changed',share_observations:0,share_changes:null,funds:[]}}/>)
    expect(screen.getByText('原份额快照已更新，旧复核已失配，需按新快照重读。')).toBeVisible()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByText(/变化 0 条/)).not.toBeInTheDocument()
  })
  it('does not turn a missing or invalid complete recheck into zero changes',()=>{
    render(<ETFSZSERecheck data={{...fixture,availability:'invalid',share_observations:0,share_changes:null,funds:[]}}/>)
    expect(screen.getByText('尚无与当前份额快照匹配且通过校验的完整重读记录。')).toBeVisible()
    expect(screen.queryByText(/重读 0 条/)).not.toBeInTheDocument()
    expect(screen.getByText('最终修订版仍待确认')).toBeVisible()
  })
})
