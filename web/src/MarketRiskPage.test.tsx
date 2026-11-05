import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {MarketRiskBanner,MarketRiskPage} from './MarketRiskPage'
import * as charts from 'lightweight-charts'
import type {MarketRiskStatus} from './types'

const fixture:MarketRiskStatus={
  contract_version:'market_risk_status_v1',parameter_version:'market_risk_parameters_v1',observation_date:'2026-11-05',generated_at:'2026-11-05T00:00:00Z',snapshot_digest:null,requested_through:null,status:'historical_only',current_risk_assessment:'not_calibrated',
  indices:[{code:'csi_all_share',name:'中证全指',through:'2026-09-03',historical_only:true,return_5d_pct:-1.54,return_20d_pct:-.49,return_60d_pct:-4.96,max_drawdown_60d_pct:-15.74,from_60d_peak_pct:-11.4,amount_5d_to_20d_ratio:null,path:[]}],
  etfs:[{code:'510300.SH',group:'沪深300',through:'2026-09-03',corporate_actions_checked:false,windows:{
    '1':{share_change_pct:1,share_change_notional_yuan:200_000,estimated_net_subscription_yuan:null,status:'corporate_actions_unchecked'},
    '5':{share_change_pct:-5,share_change_notional_yuan:-2_000_000,estimated_net_subscription_yuan:null,status:'corporate_actions_unchecked'},
    '20':{share_change_pct:null,share_change_notional_yuan:null,estimated_net_subscription_yuan:null,status:'missing'},
  }}],
  etf_aggregate:{'5':{observed_etfs:1,declared_etfs:8,estimated_net_subscription_yuan:null,reason:'未核验'}},breadth:{status:'missing'},last_attempt:{status:'failed',requested_through:'2026-11-04',reason:'provider_token_expired',completed_at:'2026-11-05T00:00:00Z'},
  parameters:{trend_windows_sessions:[5,20,60],etf_windows_sessions:[1,5,20],etf_basket:{'510300.SH':'沪深300'},risk_weights:null,risk_thresholds:null},limitations:['ETF申赎不能识别资金身份。'],sources:[],gaps:[],
}

describe('MarketRiskPage',()=>{
  afterEach(()=>{cleanup();vi.restoreAllMocks()})
  it('uses verified combined history while retaining the separately scoped SZSE source underneath',async()=>{
    const summary={listed_source_stocks:2,observed_trading_stocks:2,nontrading_stocks:0,declining_share_pct:50}
    const data:MarketRiskStatus={...fixture,combined_breadth_history:{version:'synthetic',availability:'observed',complete_market_history:true,
      historical_ST_ready:false,historical_PIT:false,effect_measured:false,covered_venues:['SSE','SZSE'],missing_venues:[],
      start:'2026-09-04',through:'2026-11-04',expected_days:2,points:[{date:'2026-09-04',all:summary,SSE:summary,SZSE:summary},{date:'2026-11-04',all:summary,SSE:summary,SZSE:summary}]},
      breadth_history:{availability:'observed',complete_market_history:false,points:[],observed_days:0,expected_days:0}}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'沪深历史涨跌分布'})).toBeInTheDocument()
    expect(screen.getByRole('slider',{name:'市场宽度观察日期'})).toBeVisible()
    expect(screen.getByText('深市名称组与原始日表来源').closest('details')).not.toHaveAttribute('open')
    expect(screen.queryByText('沪市历史仍缺')).not.toBeInTheDocument()
    expect(screen.queryByText(/沪深合并历史分布仍待补齐/)).not.toBeInTheDocument()
  })
  it('keeps a complete single-venue historical path distinct from whole-market and ST style coverage',async()=>{
    const summary={listed_source_stocks:5,observed_trading_stocks:4,nontrading_stocks:1,advancing:1,declining:2,flat:1,
      declining_5pct_or_more:0,median_return_pct:-1,declining_share_pct:50,amount_yuan:1000}
    const data:MarketRiskStatus={...fixture,breadth_history:{availability:'observed',scope:'SZSE_A_shares_daily_reports',
      start:'2026-09-04',through:'2026-11-04',observed_days:2,expected_days:2,complete_market_history:false,
      matches_market_target:false,source_url:'https://www.szse.cn/market/trend/index.html',
      note:'ST名称组按各日简称分组，不是历史法定名单或固定组合指数。',points:[
        {date:'2026-09-04',...summary,source_rows:7,excluded_b_shares:1,excluded_preferred_shares:1,st_name_group:summary},
        {date:'2026-11-04',...summary,source_rows:7,excluded_b_shares:1,excluded_preferred_shares:1,
          st_name_group:{...summary,observed_trading_stocks:0,nontrading_stocks:5,declining_share_pct:null}},
      ]}}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'深市历史涨跌分布'})).toBeInTheDocument()
    expect(screen.getByText('沪市历史仍缺')).toBeInTheDocument()
    expect(screen.getByText(/ST名称组按各日简称分组，不是历史法定名单或固定组合指数/)).toBeInTheDocument()
    expect(screen.getByText(/历史分布截止日与当前市场目标不同/)).toBeInTheDocument()
    expect(screen.getByLabelText('深市每日下跌股比例路径')).toBeInTheDocument()
    expect(screen.getByRole('columnheader',{name:'ST组下跌比例'})).toBeInTheDocument()
    expect(screen.getByRole('heading',{name:'当前无法确认'})).toBeInTheDocument()
    expect(screen.getByText('未发布')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'深交所历史日表 ↗'})).toHaveAttribute('href','https://www.szse.cn/market/trend/index.html')
  })
  it.each(['collecting','failed'])('shows retained historical collection records without a partial curve or a live-job assertion (%s)',async status=>{
    const data:MarketRiskStatus={...fixture,breadth_history:{availability:'missing',complete_market_history:false,points:[],
      last_recorded_attempt:{status,recorded_at:'2026-11-05T00:00:00Z',start:'2026-09-04',requested_through:'2026-11-04',completed_days:2,expected_days:38}}}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByText(/最近采集记录已核对 2\/38 个日期/)).toBeInTheDocument()
    expect(screen.getByText(/历史窗尚未完整发布，暂不展示缩短的曲线/)).toBeInTheDocument()
    expect(screen.queryByLabelText('深市每日下跌股比例路径')).not.toBeInTheDocument()
    expect(screen.queryByText(/采集正在运行/)).not.toBeInTheDocument()
    if(status==='failed')expect(screen.getByText(/最近一次采集中断，已核对日期保留用于续采/)).toBeInTheDocument()
  })
  it('keeps quarterly share disclosures, dashes and off-exchange scope distinct from current cash flow',async()=>{
    const data:MarketRiskStatus={...fixture,etf_quarterly:{version:'etf_quarterly_share_accounting_v1',availability:'observed',
      period_label:'2026Q3',period_start:'2026-07-01',period_end:'2026-09-30',observed_reports:2,declared_etfs:8,corporate_actions_checked:false,
      note:'季报申赎为整个季度的份额披露，不是近两个月的资金金额。',reports:[
        {code:'159919.SZ',availability:'observed',net_subscription_shares:'-72900000.00',split_entry:'-',accounting_residual_shares:'0.00'},
        {code:'510310.SH',availability:'observed',publication_date:'2026-10-27',source_url:'https://www.sse.com.cn/report.pdf',
          pdf_url:'https://www.sse.com.cn/report.pdf',table_page:13,net_subscription_shares:'387000000.00',split_entry:'-',
          accounting_residual_shares:'0.00',off_exchange_closing_shares:'44159905',audit_status:'report_states_unaudited',
          daily_comparison:{availability:'observed',date:'2026-09-30',reported_shares:'11987744000.0',difference_from_report_total:'-44159922.00',
            difference_after_explicit_off_exchange:'-17.00',source_rounding_rule:'not_confirmed'}},
      ]}}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'季报申赎与日表范围核对'})).toBeInTheDocument()
    expect(screen.getByText('-72,900,000.00 份')).toBeInTheDocument()
    expect(screen.getByText(/季报期末总额明确包含场外 44,159,905 份/)).toBeInTheDocument()
    expect(screen.getByText(/从季报总额扣除明示场外份额后，与日表差 -17.00 份/)).toBeInTheDocument()
    expect(screen.getAllByText('横线不自动改写为零事件')).toHaveLength(2)
    expect(screen.getByRole('link',{name:'季报 · PDF第13页 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/report.pdf#page=13')
    expect(screen.getByText('未发布')).toBeInTheDocument()
  })
  it('displays catalog coverage and cancellation material while leaving event conclusions unverified',async()=>{
    const data:MarketRiskStatus={...fixture,etf_announcements:{availability:'observed',through:'2026-11-05',
      window_start:'2026-08-04',window_end:'2026-11-04',catalog_etfs:8,declared_etfs:8,record_count:2468,review_required_count:105,
      corporate_actions_checked:false,note:'目录取得不代表事件已核验。',fulltext:{availability:'observed',required:105,text_available:105,missing_or_unreadable:0,semantic_review:'not_reconciled'},catalogs:[{code:'512100.SH',source_url:'https://www.sse.com.cn/disclosure/fund/announcement/',
      record_count:300,oldest_publication:'2016-08-19',newest_publication:'2026-10-29',review_required_count:1,review_status:'not_reconciled',
      required_documents:[{document_id:'cancel',code:'512100.SH',published_on:'2022-07-30',title:'取消基金份额拆分的公告',url:'https://www.sse.com.cn/cancel.pdf',review_reason:'historical_share_title'}]}]}}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByText('目录 8/8')).toBeInTheDocument()
    expect(screen.getByText(/已取得目录 2,468 条；待核对文档 105 份/)).toBeInTheDocument()
    expect(screen.getByText(/已提取文本 105 \/ 105 份；缺失或不可读 0 份/)).toBeInTheDocument()
    expect(screen.getByText(/文本提取不代表逐页完整或份额事件核验通过/)).toBeInTheDocument()
    expect(screen.getByText('全文与生效日尚未完成核对')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'取消基金份额拆分的公告 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/cancel.pdf')
    expect(screen.getByText('历史份额相关标题',{exact:false})).toBeInTheDocument()
    expect(screen.getByText('未发布')).toBeInTheDocument()
  })
  it('marks historical values and expired updates before showing trend data',async()=>{
    vi.spyOn(globalThis,'fetch').mockImplementation(async()=>new Response(JSON.stringify(fixture)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'当前无法确认'})).toBeInTheDocument()
    expect(screen.getByText(/行情接口凭证已过期/)).toBeInTheDocument()
    expect(screen.getByText(/中证全指 · 截至 2026-09-03 · 历史快照/)).toBeInTheDocument()
    expect(screen.getByText('-15.74%')).toBeInTheDocument()
    expect(screen.getByText('当日涨跌分布尚未取得，无法判断同步下跌的范围。')).toBeInTheDocument()
  })
  it('switches ETF windows while withholding unverified redemption amounts',async()=>{
    vi.spyOn(globalThis,'fetch').mockImplementation(async()=>new Response(JSON.stringify(fixture)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByText('-5.00%')).toBeInTheDocument()
    expect(screen.getByText('未发布')).toBeInTheDocument()
    expect(screen.getByText('份额事件未核验')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox',{name:'ETF观察窗口'}),{target:{value:'1'}})
    expect(screen.getByText('+1.00%')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'60日'}))
    expect(screen.getByRole('button',{name:'60日'})).toHaveAttribute('aria-pressed','true')
  })
  it('keeps the market precheck visible even when its data endpoint fails',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response('',{status:503}))
    render(<MemoryRouter><MarketRiskBanner/></MemoryRouter>)
    expect(screen.getByText('大盘数据尚未确认，当前风险未知。')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:/ETF、市场走势与流动性/})).toHaveAttribute('href','/market')
  })
  it('discloses complete issuer NAV coverage while keeping flow estimates unpublished',async()=>{
    const data:MarketRiskStatus={...fixture,
      issuer_nav_snapshot:{availability:'observed',through:'2026-11-04'},
      etfs:[{...fixture.etfs[0],nav_through:'2026-11-04',nav_source:'嘉实',nav_source_url:'https://www.jsfund.cn/',nav_crosscheck_observations:10}],
      etf_aggregate:{'5':{observed_etfs:8,nav_observed_etfs:8,declared_etfs:8,estimated_net_subscription_yuan:null,reason:'未核验'}},
    }
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByText(/同窗单位净值覆盖 8\/8/)).toBeInTheDocument()
    expect(screen.getByText(/基金公司历史净值截至 2026-11-04/)).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'嘉实单位净值 ↗'})).toHaveAttribute('href','https://www.jsfund.cn/')
    expect(screen.getByText('已与交易所核对 10 个重叠净值日')).toBeInTheDocument()
    expect(screen.getByText('未发布')).toBeInTheDocument()
    expect(screen.getByText('份额事件未核验')).toBeInTheDocument()
  })
  it('shows independent public share coverage while the current market remains unknown',async()=>{
    const data:MarketRiskStatus={...fixture,
      public_etf_snapshot:{availability:'observed',through:'2026-11-04'},
      etf_aggregate:{'5':{observed_etfs:5,nav_observed_etfs:0,declared_etfs:8,evaluation_through:'2026-11-04',estimated_net_subscription_yuan:null,reason:'未核验'}},
      etfs:[{...fixture.etfs[0],source:'sse_public',through:'2026-11-04',windows:{
        ...fixture.etfs[0].windows,
        '5':{share_change_pct:-5,share_change_ten_thousand:-50,share_change_notional_yuan:null,estimated_net_subscription_yuan:null,status:'shares_only'},
      }}],
    }
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'当前无法确认'})).toBeInTheDocument()
    expect(screen.getByText(/同窗份额覆盖 5\/8，目标截至 2026-11-04/)).toBeInTheDocument()
    expect(screen.getByText('上交所日终公布份额')).toBeInTheDocument()
    expect(screen.getByText('份额已取得；净值与份额事件待核验')).toBeInTheDocument()
    expect(screen.getByText('-50 万份')).toBeInTheDocument()
    expect(screen.getByRole('combobox',{name:'ETF份额路径'})).toBeInTheDocument()
    expect(screen.getByText('未发布')).toBeInTheDocument()
  })
  it('keeps old ST history off the current index chart and discloses provisional SZSE shares',async()=>{
    const addSeries=vi.fn(()=>({setData:vi.fn()}))
    vi.spyOn(charts,'createChart').mockImplementation(()=>({addSeries,timeScale:()=>({fitContent:vi.fn()}),remove:vi.fn()}) as unknown as ReturnType<typeof charts.createChart>)
    const path=Array.from({length:21},(_,i)=>({date:`2026-10-${String(i+1).padStart(2,'0')}`,close:100+i}))
    const data:MarketRiskStatus={...fixture,status:'observed_snapshot',requested_through:'2026-11-04',
      market_coverage:{indices_observed_at_target:3,declared_indices:3,st_style_at_target:false,breadth_at_target:false},
      public_index_snapshot:{availability:'observed',through:'2026-11-04',scope:'three_price_indices_only'},
      szse_etf_snapshot:{availability:'observed',through:'2026-11-04',share_revision_status:'final_revision_unverified'},
      indices:[...['中证全指','沪深300','中证2000'].map((name,i)=>({...fixture.indices[0],code:`index-${i}`,name,through:'2026-11-04',historical_only:false,path})),
        {...fixture.indices[0],code:'st_equal_weight_v1',name:'ST等权研究指数',path}],
      parameters:{...fixture.parameters,etf_basket:{'159919.SZ':'沪深300'}},
      etfs:[{...fixture.etfs[0],code:'159919.SZ',source:'szse_public',through:'2026-11-04',nav_through:'2026-11-03',share_revision_unverified:true}],
      etf_aggregate:{'5':{observed_etfs:8,revision_unconfirmed_etfs:3,declared_etfs:8,estimated_net_subscription_yuan:null,reason:'未核验'}},
    }
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByText('同日市场指数 3/3；沪深整体同期ST走势未覆盖；涨跌分布未覆盖。')).toBeInTheDocument()
    expect(screen.getByText(/ST等权研究指数 · 截至 2026-09-03 · 历史快照 · 未入同期图/)).toBeInTheDocument()
    expect(addSeries).toHaveBeenCalledTimes(3)
    expect(screen.getByText(/3只ETF的最新份额修订状态待核对/)).toBeInTheDocument()
    expect(screen.getByText('净值截至 2026-11-03')).toBeInTheDocument()
    expect(screen.getByText('最新份额最终修订版仍待确认')).toBeInTheDocument()
  })
  it('defaults to an explicitly dated two-calendar-month window',async()=>{
    const recent={start:'2026-09-04',end:'2026-11-04',sessions:37,return_pct:-20,max_drawdown_pct:-20,from_peak_pct:-20}
    const path=Array.from({length:62},(_,i)=>new Date(Date.UTC(2026,8,4+i)))
      .filter(day=>![0,6].includes(day.getUTCDay())&&day.toISOString().slice(0,10)!=='2026-09-25'&&!(day.getUTCMonth()===9&&day.getUTCDate()<=7))
      .map((day,i)=>({date:day.toISOString().slice(0,10),close:100-i*20/37}))
    const data:MarketRiskStatus={...fixture,status:'observed_snapshot',requested_through:'2026-11-04',
      recent_window:{availability:'defined',start:recent.start,end:recent.end,sessions:37,points:38},
      indices:[{...fixture.indices[0],historical_only:false,through:'2026-11-04',recent,path}],
      etfs:[{...fixture.etfs[0],path:path.map(point=>({date:point.date,shares:point.close})),windows:{...fixture.etfs[0].windows,
        recent:{window_sessions:37,window_start:recent.start,window_end:recent.end,share_change_pct:-20,share_change_notional_yuan:null,estimated_net_subscription_yuan:null,status:'shares_only'},
      }}],
      etf_aggregate:{...fixture.etf_aggregate,recent:{observed_etfs:1,declared_etfs:8,estimated_net_subscription_yuan:null,reason:'未核验'}},
    }
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByRole('button',{name:'近2个月'})).toHaveAttribute('aria-pressed','true')
    expect(screen.getByRole('combobox',{name:'ETF观察窗口'})).toHaveValue('recent')
    expect(screen.getByText(/近两个月：2026-09-04 至 2026-11-04，37个交易日跨度/)).toBeInTheDocument()
    expect(screen.getByLabelText('近两个月市场基准归一化路径')).toBeInTheDocument()
    expect(screen.getByLabelText('510300.SH 近两个月公布份额归一化路径')).toBeInTheDocument()
    expect(screen.getByText(/尚未完成节点与大盘因素的独立对照/)).toBeInTheDocument()
  })
  it('keeps two-exchange daily breadth and the current ST name group separate from historical style',async()=>{
    const summary={listed_source_stocks:5,observed_trading_stocks:3,nontrading_stocks:2,advancing:0,declining:2,flat:1,
      declining_5pct_or_more:2,median_return_pct:-10,declining_share_pct:66.666667,amount_yuan:195010}
    const data:MarketRiskStatus={...fixture,breadth:{status:'observed',source:'exchange_public',through:'2026-11-04',scope:'沪深A股；不含北交所。',
      historical_path_available:false,...summary,
      venues:[{venue:'SSE',label:'上交所股票行情',url:'https://www.sse.com.cn/market/price/report/',source_rows:4,excluded_b_shares:1,through:'2026-11-04',...summary}],
      st_name_group:{definition:'只按当日证券简称分组，不重建历史成员。',listed_source_stocks:3,observed_trading_stocks:1,advancing:0,declining:0,median_return_pct:0,mean_return_pct:0},
    }}
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify(data)))
    render(<MemoryRouter><MarketRiskPage/></MemoryRouter>)
    expect(await screen.findByText('下跌占有成交股票')).toBeInTheDocument()
    expect(screen.getByText('66.67%')).toBeInTheDocument()
    expect(screen.getByText(/当前只有 2026-11-04 的收盘截面，近两个月的涨跌分布路径仍待补齐/)).toBeInTheDocument()
    expect(screen.getByRole('columnheader',{name:'剔除B股'})).toBeInTheDocument()
    expect(screen.getByRole('heading',{name:'ST名称分组 · 当日分布'})).toBeInTheDocument()
    expect(screen.getByText(/同期ST走势仍需历史成员与价格数据/)).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'上交所股票行情 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/market/price/report/')
  })
})
