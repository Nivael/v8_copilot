import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {MarketRiskBanner,MarketRiskPage} from './MarketRiskPage'
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
})
