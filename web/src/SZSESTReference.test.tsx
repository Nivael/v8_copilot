import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it} from 'vitest'
import type {MarketRiskIndex,SZSESTReference as Reference} from './types'
import {SZSESTReference} from './SZSESTReference'

// Synthetic paths exercise window matching and missingness, not current real market facts.
const points=[{date:'2026-09-04',close:1000,member_count:20,observed_members:20,coverage_ratio:1,missing_symbols:[],daily_return_pct:0},
  {date:'2026-09-07',close:900,member_count:20,observed_members:19,coverage_ratio:.95,missing_symbols:['000001.SZ'],daily_return_pct:-10},
  {date:'2026-09-08',close:950,member_count:20,observed_members:20,coverage_ratio:1,missing_symbols:[],daily_return_pct:100/18}]
const data:Reference={availability:'observed',start:'2026-09-04',through:'2026-09-08',anchor_on:'2026-09-03',anchor_members:20,
  distinct_members:21,endpoint_members:20,reviewed_transitions:1,minimum_coverage:.95,coverage_threshold:.95,return_pct:-5,max_drawdown_pct:-10,
  endpoint_list_observed_on:'2026-09-09',combined_ST_ready:false,effect_measured:false,points,
  events:[{symbol:'000001',old_name:'ST样本',new_name:null,kind:'listing_end',effective_on:'2026-09-08',source_url:'https://static.cninfo.com.cn/synthetic.PDF',proof_page:2,observed_at:'2026-11-05T04:00:00+00:00'}]}
const baseline:MarketRiskIndex={code:'000985.CSI',name:'中证全指',through:'2026-09-08',historical_only:false,return_5d_pct:null,
  return_20d_pct:null,return_60d_pct:null,max_drawdown_60d_pct:null,from_60d_peak_pct:null,amount_5d_to_20d_ratio:null,
  path:points.map((p,i)=>({date:p.date,close:100+i*2}))}

describe('SZSESTReference',()=>{
  afterEach(cleanup)
  it('compares only a complete matching window and keeps the scope descriptive',()=>{
    render(<SZSESTReference data={data} indices={[baseline]}/> )
    expect(screen.getByText('交易所覆盖 1/2 · 仅深市')).toBeVisible()
    expect(screen.getByText('中证全指 · 同窗')).toBeVisible()
    expect(screen.getByText('-5.00%')).toBeVisible()
    expect(screen.getByText('-10.00%')).toBeVisible()
    expect(screen.getByText(/不是组合财富或全收益/)).toBeVisible()
    expect(screen.getByText(/不能证明市场因素优于节点/)).toBeVisible()
  })
  it('lets keyboard or pointer selection inspect each day and its nontrading members',()=>{
    render(<SZSESTReference data={data} indices={[baseline]}/> )
    const slider=screen.getByRole('slider',{name:'ST参考观察日期'})
    fireEvent.change(slider,{target:{value:'1'}})
    expect(slider).toHaveAttribute('aria-valuetext','2026-09-07')
    expect(screen.getByText('ST参考 90.00 · 中证全指 102.00')).toBeVisible()
    expect(screen.getByText('成员 20 · 有成交 19 · 覆盖 95.00%')).toBeVisible()
    expect(screen.getByText('停牌或缺失：000001.SZ')).toBeVisible()
  })
  it.each(['older','missing_day','different_calendar','null_price'])('does not overlay an inconsistent market series: %s',bad=>{
    const copy={...baseline,path:baseline.path.map(p=>({...p}))}
    if(bad==='older')copy.through='2026-09-03'
    else if(bad==='missing_day')copy.path.splice(1,1)
    else if(bad==='different_calendar')copy.path[1].date='2026-09-06'
    else copy.path[1].close=null
    render(<SZSESTReference data={data} indices={[copy]}/> )
    expect(screen.getByText(/当前不叠加市场对照线/)).toBeVisible()
    expect(screen.queryByText('中证全指 · 同窗')).not.toBeInTheDocument()
    expect(screen.getByRole('img',{name:'深市ST价格参考路径'})).toBeVisible()
  })
  it.each(['invalid','source_changed','insufficient_coverage'])('hides the whole path and old metrics if %s',availability=>{
    render(<SZSESTReference data={{...data,availability}} indices={[baseline]}/> )
    expect(screen.getByText(/整段曲线与窗口指标均不发布/)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByText('-5.00%')).not.toBeInTheDocument()
    expect(screen.queryByText('交易所覆盖 1/2 · 仅深市')).not.toBeInTheDocument()
  })
  it('does not silently bridge a missing ST close',()=>{
    render(<SZSESTReference data={{...data,points:points.map((p,i)=>({...p,close:i===1?null:p.close}))}} indices={[baseline]}/> )
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
  })
  it('links the effective-date proof to its physical PDF page and separates the later list read',()=>{
    render(<SZSESTReference data={data} indices={[]}/> )
    fireEvent.click(screen.getByText('查看成员生效依据与每日覆盖'))
    expect(screen.getByRole('link',{name:'原PDF第2页 ↗'})).toHaveAttribute('href','https://static.cninfo.com.cn/synthetic.PDF#page=2')
    expect(screen.getByText(/该次读取日期不回填为历史名单日期/)).toBeVisible()
    expect(screen.getByText('摘牌')).toBeVisible()
    expect(screen.getByRole('region',{name:'可滚动的ST成员生效依据表'})).toHaveAttribute('tabindex','0')
    expect(screen.getByRole('region',{name:'可滚动的ST逐日成交覆盖表'})).toHaveAttribute('tabindex','0')
  })
})
