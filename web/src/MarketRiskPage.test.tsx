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
    expect(screen.getByText('上交所日终总份额')).toBeInTheDocument()
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
    expect(await screen.findByText('同日市场指数 3/3；同期ST风格未覆盖；涨跌分布未覆盖。')).toBeInTheDocument()
    expect(screen.getByText(/ST等权研究指数 · 截至 2026-09-03 · 历史快照 · 未入同期图/)).toBeInTheDocument()
    expect(addSeries).toHaveBeenCalledTimes(3)
    expect(screen.getByText(/3只ETF的最新份额修订状态待核对/)).toBeInTheDocument()
    expect(screen.getByText('净值截至 2026-11-03')).toBeInTheDocument()
    expect(screen.getByText('最新份额待次日修订核对')).toBeInTheDocument()
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
    expect(screen.getByLabelText('510300.SH 近两个月总份额归一化路径')).toBeInTheDocument()
    expect(screen.getByText(/尚未完成节点与大盘因素的独立对照/)).toBeInTheDocument()
  })
})
