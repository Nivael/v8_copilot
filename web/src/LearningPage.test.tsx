import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {LearningPage} from './LearningPage'
import type {LearningStatus} from './types'

const payload:LearningStatus={
  contract_version:'v8_learning_status_v1',generated_at:'2026-11-05T01:00:00Z',observation_date:'2026-11-05',timezone:'Asia/Shanghai',
  availability:{experiences:'available'},gaps:[],
  counts:{accepted:9,candidate:1,blocked:0,ignored:0,merged:0,closed:0,superseded:0},
  runs:{total:42,validator_passed:42,with_experience_hits:15,latest_at:'2026-09-09T00:00:00Z'},
  regression_counts:{current:0,due:0,never_checked:9,needs_recheck:0,unverified:0,failed:0},
  latest_regression:{run_id:'XRG-TEST',completed_at:'2026-07-21T00:00:00Z',accepted_examined:0,passed:0,failed:0,unverified:0},
  conflicts:[],methods:[{
    experience_id:'EXP-AAA',title:'先统一主体',status:'accepted',experience_version:2,
    source_ref_count:3,existing_source_runs:2,validator_passed_source_runs:2,unresolved_source_refs:['migration:old'],
    unsupported_validation_refs:[],blocking_conflict:false,regression_state:'never_checked',last_checked_at:null,next_due_at:null,reviewed_at:'2026-08-12T00:00:00Z',reviewed_by:'owner',
  },{
    experience_id:'EXP-BBB',title:'节点沉默拆分',status:'candidate',experience_version:1,
    source_ref_count:1,existing_source_runs:1,validator_passed_source_runs:1,unresolved_source_refs:[],
    unsupported_validation_refs:['pack:EP-1'],blocking_conflict:false,regression_state:'never_checked',last_checked_at:null,next_due_at:null,reviewed_at:null,reviewed_by:null,
  }],
  freshness:{availability:'available',manifest_id:'FM-TEST',generated_at:'2026-09-08T00:00:00Z',research_symbol_count:203,universe_as_of:'2026-09-07',
    sources:[{source_id:'daily_prices',label:'日线价格',as_of:'2026-09-07',checked_at:'2026-09-08',expected_through:'2026-09-07',declared_status:'current',age_calendar_days:59,row_count:100,coverage_count:9,source_ref:'daily_prices'}]},
  quality_evaluation:{status:'not_measured',accuracy:null,reason:'没有独立留出题集，不能说明准确率。'},
  automation:{promotion:'on_candidate_or_feedback',minimum_source_runs:2,periodic_verification:'explicit_command',schedule_status:'not_observed'},read_only:true,not_evidence:true,
}

function open(){return render(<MemoryRouter><LearningPage/></MemoryRouter>)}
describe('LearningPage',()=>{
  afterEach(()=>{cleanup();vi.restoreAllMocks()})
  it('separates accepted inventory from current verification and empty batches',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(payload)))
    open()
    const ledger=await screen.findByRole('region',{name:'改进闭环库存'})
    expect(within(ledger).getByText('9')).toBeInTheDocument()
    expect(within(ledger).getByText('0')).toBeInTheDocument()
    expect(screen.getByText('效果尚未测量')).toBeInTheDocument()
    expect(screen.getByText(/空批次不能证明库存已验证/)).toBeInTheDocument()
    expect(screen.getAllByText('尚未复验')).toHaveLength(2)
    expect(screen.getByText('59 天')).toBeInTheDocument()
    expect(screen.getByText('current')).toBeInTheDocument()
    expect(screen.getByText(/有效来源 1\/2/)).toBeInTheDocument()
    expect(screen.getByRole('link',{name:/追溯回答/})).toHaveAttribute('href','/runs')
  })
  it('filters method rows and rereads without any mutation request',async()=>{
    const fetch=vi.spyOn(globalThis,'fetch').mockImplementation(async()=>new Response(JSON.stringify(payload)))
    open()
    await screen.findByText('先统一主体')
    fireEvent.change(screen.getByRole('searchbox',{name:'查找方法'}),{target:{value:'节点'}})
    expect(screen.queryByText('先统一主体')).not.toBeInTheDocument()
    expect(screen.getByText('节点沉默拆分')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox',{name:'状态'}),{target:{value:'accepted'}})
    expect(screen.getByText('没有符合筛选条件的方法。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'重新核对'}))
    await screen.findByRole('button',{name:'重新核对'})
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(fetch.mock.calls.every(call=>call[1]?.method===undefined)).toBe(true)
  })
  it('shows unknown values for missing sources and allows retry after request failure',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValueOnce(new Response('',{status:503}))
      .mockResolvedValueOnce(new Response(JSON.stringify({...payload,counts:null,runs:null,regression_counts:null,methods:[],gaps:['experiences:missing']})))
    open()
    expect(await screen.findByRole('alert')).toHaveTextContent('未读到的库存不会显示为零')
    fireEvent.click(screen.getByRole('button',{name:'重新核对'}))
    expect(await screen.findByText('经验库不可读，无法核对方法。')).toBeInTheDocument()
    const ledger=screen.getByRole('region',{name:'改进闭环库存'})
    expect(within(ledger).queryByText('0')).not.toBeInTheDocument()
    expect(within(ledger).getAllByText('—').length).toBeGreaterThan(0)
  })
  it('keeps new market source dates separate from the old stock manifest',async()=>{
    const data:LearningStatus={...payload,market_updates:[{
      source_id:'szse_nav',label:'深交所 · ETF净值',availability:'observed',requested_through:'2026-11-04',
      observed_through_min:'2026-11-03',observed_through_max:'2026-11-03',observation_count:30,
      series_at_target:0,declared_series:3,snapshot_digest:'abc',url:'https://fund.szse.cn/marketdata/etf/',fetched_at:'2026-11-05T00:00:00Z',note:'实际净值日期，不补值。',
    }]}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    open()
    const section=await screen.findByRole('region',{name:'市场来源更新'})
    expect(within(section).getByText('2026-11-03')).toBeInTheDocument()
    expect(within(section).getByText('30 条')).toBeInTheDocument()
    expect(within(section).getByText('目标日期覆盖 0/3 条序列')).toBeInTheDocument()
    expect(screen.getByText('59 天')).toBeInTheDocument()
    expect(within(section).getByRole('link',{name:/查看大盘环境/})).toHaveAttribute('href','/market')
  })
  it('labels an announcement search cutoff instead of presenting it as a new publication date',async()=>{
    const data:LearningStatus={...payload,market_updates:[{source_id:'etf_announcements',label:'ETF公告目录 · 待事件核验',
      availability:'observed',requested_through:'2026-11-05',observed_through_min:'2026-11-05',observed_through_max:'2026-11-05',
      observation_count:2468,series_at_target:8,declared_series:8,snapshot_digest:'abc',url:'/market',fetched_at:'2026-11-05T00:00:00Z',
      date_basis:'catalog_search_cutoff',note:'目录取得不代表份额事件已核验。'}]}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    open()
    expect(await screen.findByText('检索至 2026-11-05')).toBeInTheDocument()
    expect(screen.getByText('目录取得不代表份额事件已核验。')).toBeInTheDocument()
  })
  it('counts a historical price archive by security originals without asserting date completeness',async()=>{
    const data:LearningStatus={...payload,market_updates:[{source_id:'sse_historical_price_archive',label:'沪市历史价格来源',availability:'observed',
      requested_through:'2026-11-04',observed_through_min:'2026-09-04',observed_through_max:'2026-11-04',observation_count:78,
      observation_unit:'有成交股票日',coverage_basis:'price_archives',date_basis:'historical_price_archive',series_at_target:null,
      observed_source_groups:3,declared_series:3,snapshot_digest:'synthetic',url:'/market',fetched_at:'2026-11-05T05:00:00Z',note:'缺日待核，历史分布与ST未发布。'}]}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)));open()
    const section=await screen.findByRole('region',{name:'市场来源更新'})
    expect(within(section).getByText('78 有成交股票日')).toBeInTheDocument()
    expect(within(section).getByText('价格原件 3/3 只证券')).toBeInTheDocument()
    expect(within(section).getByText('价格记录窗 2026-09-04 至 2026-11-04')).toBeInTheDocument()
    expect(within(section).queryByText(/目标日期覆盖/)).not.toBeInTheDocument()
  })
  it('keeps partially explained missing-day episodes separate from venue coverage',async()=>{
    const data:LearningStatus={...payload,market_updates:[{source_id:'sse_missing_day_review',label:'沪市缺日核对',availability:'partial',
      requested_through:'2026-11-04',observed_through_min:'2026-09-04',observed_through_max:'2026-11-04',observation_count:148,
      observation_unit:'已解释的缺失股票日',coverage_basis:'missing_day_episodes',date_basis:'historical_notice_review',series_at_target:null,
      observed_source_groups:23,declared_series:25,snapshot_digest:'synthetic',url:'/market',fetched_at:'2026-11-05T06:00:00Z',note:'区间待补，不提升沪深历史覆盖。'}]}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)));open()
    const section=await screen.findByRole('region',{name:'市场来源更新'})
    expect(within(section).getByText('148 已解释的缺失股票日')).toBeInTheDocument()
    expect(within(section).getByText('完整区间 23/25 组')).toBeInTheDocument()
    expect(within(section).getByText('已核对部分依据')).toBeInTheDocument()
    expect(within(section).getByText('公告核对窗 2026-09-04 至 2026-11-04')).toBeInTheDocument()
    expect(within(section).queryByText(/目标日期覆盖/)).not.toBeInTheDocument()
  })
  it('distinguishes member-day records from venue coverage',async()=>{
    const data:LearningStatus={...payload,market_updates:[{source_id:'szse_st_price_reference',label:'深市ST价格参考',availability:'observed',
      requested_through:'2026-11-04',observed_through_min:'2026-09-04',observed_through_max:'2026-11-04',observation_count:4416,
      observation_unit:'成员日',coverage_unit:'交易所',series_at_target:1,declared_series:2,snapshot_digest:'synthetic',url:'/market',
      fetched_at:'2026-11-05T04:00:00Z',note:'每日成员合计，包含停牌分母；不同成员数另列。'}]}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)));open()
    const section=await screen.findByRole('region',{name:'市场来源更新'})
    expect(within(section).getByText('4,416 成员日')).toBeInTheDocument()
    expect(within(section).getByText('目标日期覆盖 1/2 交易所')).toBeInTheDocument()
    expect(within(section).queryByText('4,416 条')).not.toBeInTheDocument()
    expect(screen.getByText('59 天')).toBeInTheDocument()
  })
  it('labels current-list reads separately from dated source coverage',async()=>{
    const data:LearningStatus={...payload,market_updates:[{source_id:'exchange_risk_membership',label:'交易所名单',availability:'observed',
      requested_through:null,observed_through_min:null,observed_through_max:null,observation_count:199,series_at_target:null,declared_series:6,
      observed_source_groups:6,observation_date:'2026-11-05',snapshot_digest:'abc',url:'/market',fetched_at:'2026-11-05T03:49:15Z',
      date_basis:'current_list_observation',note:'读取日非统一数据截止日，不推进历史成员日期。'}]}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)));open()
    const section=await screen.findByRole('region',{name:'市场来源更新'})
    expect(within(section).getByText('读取于 2026-11-05')).toBeInTheDocument()
    expect(within(section).getByText('本次读取 6/6 张分类表')).toBeInTheDocument()
    expect(within(section).getByRole('region',{name:'可滚动的市场来源更新表'})).toHaveAttribute('tabindex','0')
    expect(within(section).queryByText(/目标日期覆盖/)).not.toBeInTheDocument()
    expect(screen.getByText('59 天')).toBeInTheDocument()
  })
  it('separates reconstructed price sources from independently checked daily membership',async()=>{
    const data:LearningStatus={...payload,market_updates:[{source_id:'combined_ST_reconstruction',label:'沪深ST重建参考',availability:'reconstructed',
      requested_through:'2026-11-04',observed_through_min:'2026-09-04',observed_through_max:'2026-11-04',observation_count:7529,
      observation_unit:'成员日（重建）',coverage_basis:'ST_reconstruction',series_at_target:null,observed_source_groups:2,verified_membership_venues:1,
      declared_series:2,snapshot_digest:'synthetic',url:'/market',fetched_at:'2026-11-05T04:00:00Z',note:'沪市逐日成员尚待独立核验。'}]}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)));open()
    const section=await screen.findByRole('region',{name:'市场来源更新'})
    expect(within(section).getByText('价格来源 2/2；逐日成员核验 1/2')).toBeInTheDocument()
    expect(within(section).getByText('重建参考，成员待核')).toBeInTheDocument()
    expect(within(section).getByText('7,529 成员日（重建）')).toBeInTheDocument()
    expect(within(section).queryByText(/目标日期覆盖/)).not.toBeInTheDocument()
  })
})
