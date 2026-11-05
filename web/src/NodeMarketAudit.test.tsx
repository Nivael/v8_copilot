import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import {NodeMarketAudit} from './NodeMarketAudit'
import type {NodeMarketInputAudit} from './types'

const fixture:NodeMarketInputAudit={version:'node_market_input_audit_v1',availability:'observed',outcomes_read:false,effect_measured:false,
  observed_at:'2026-11-05T03:16:48+00:00',
  plan:{minimum_test_events:100,minimum_test_companies:40,horizon_sessions:20,anchor_start:'2021-03-17',anchor_end:'2025-12-31'},
  test_capacity_events:9,test_capacity_companies:5,active_run_linked_events:553,event_table_rows:791,unbound_table_rows:238,
  source_kind_counts:{p6a_verified_fact:91,official_title_exact:462},p6_run:{verified_event_count:685},main_window_nominations:89,
  latest_deterministic_events:400,deterministic_lineage_counts:{active_prior_fact:22,active_title:314,not_bound_to_active_run:64},
  conservative_date_shifts:4,issues:{publication_date_hint_conflict:75,one_source_price_keys_incomplete:21},notice:'来源对齐不代表本轮重审正文。',
  date_reviews:[{document_id:'cninfo:1213499094',company:'花王生态工程股份有限公司',symbol:'603007',signed_on:'2022-05-26',availability:'observed',source_url:'https://static.cninfo.com.cn/finalpage/2022-05-26/1213499094.PDF',signature_page:3}],
  folds:[{test_year:2023,train_events:1,train_companies:1,test_events:3,test_companies:2,train_capacity_pass:false}],
  source_dates:{benchmark_keys_through:'2026-09-03',historical_membership_through:'2026-09-03',node_information_through:'2026-06-26',price_keys_through:{base_qfq_complete_window:'2026-09-07',p8_qfq_complete_window:'2026-09-03'}}}

function open(){fireEvent.click(screen.getByText('查看样本来源、时间核对与预定对照'))}

describe('NodeMarketAudit',()=>{
  afterEach(cleanup)
  it('reports input capacity without claiming measured accuracy or a fitted comparison',()=>{
    render(<NodeMarketAudit data={fixture}/>)
    expect(screen.getByText(/仅 9 条、5 家公司/)).toBeVisible()
    expect(screen.getByText(/预定最低 100 条、40 家/)).toBeVisible()
    expect(screen.getByText(/尚未读取价格值、计算结果或拟合模型/)).toBeVisible()
    expect(screen.getByText('效果尚未测量')).toBeVisible()
  })
  it('keeps active-run, accumulated-table and label lineage denominators distinct',()=>{
    render(<NodeMarketAudit data={fixture}/>);open()
    expect(screen.getByText(/本轮P6运行绑定 553 条节点，其中原事实链 91 条、精确标题来源 462 条/)).toBeVisible()
    expect(screen.getByText(/另有 238 条未绑定本轮/)).toBeVisible()
    expect(screen.getByText(/标签共 400 条：22 条连到本轮既有事实链、314 条连到标题来源、64 条未对齐/)).toBeVisible()
    expect(screen.getByText(/这个标签不等于正文已核证/)).toBeVisible()
    expect(screen.getByText(/不相加作剔除总数/)).toBeVisible()
  })
  it('links to the reviewed signature page while preserving conservative-date meaning',()=>{
    render(<NodeMarketAudit data={fixture}/>);open()
    expect(screen.getByRole('link',{name:'原始PDF第3页 ↗'})).toHaveAttribute('href',fixture.date_reviews?.[0].source_url+'#page=3')
    expect(screen.getByText('2022-05-26')).toBeVisible()
    expect(screen.getByText(/事件发生日保留，未恢复精确发布时间/)).toBeVisible()
    expect(screen.getByText('训练数量不足')).toBeVisible()
  })
  it('preserves historical source dates and discloses untested ETF factors and recent gaps',()=>{
    render(<NodeMarketAudit data={fixture}/>);open()
    expect(screen.getByText(/本轮未检验ETF申赎因子，也未测量方法效果/)).toBeVisible()
    expect(screen.getByText(/个股内核价格键止于 2026-09-07/)).toBeVisible()
    expect(screen.getByText(/尚不能覆盖最近两个月压力案例/)).toBeVisible()
    expect(screen.getByText(/这是盘点时间，来源数据各自的截止日另列/)).toBeVisible()
    expect(screen.getByText(/左右滑动下方表格可查看公告来源/)).toBeVisible()
    expect(screen.getByRole('region',{name:'可滚动的时间留出容量表'})).toHaveAttribute('tabindex','0')
  })
  it('does not reuse stale counts when inputs change',()=>{
    render(<NodeMarketAudit data={{...fixture,availability:'source_changed'}}/>)
    expect(screen.getByText('来源已变化，旧盘点失配，需重新执行；尚不显示旧样本数。')).toBeVisible()
    expect(screen.queryByText(/仅 9 条/)).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
