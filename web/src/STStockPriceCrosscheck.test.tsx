import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {STStockPriceCrosscheck} from './STStockPriceCrosscheck'
import type {PriceCheckWindow,RegimeStockPriceCheck} from './stRegimeTypes'
const w:PriceCheckWindow={anchor:'2026-07-03',through:'2026-11-06',market_days:84,stock_pct:-10,reference_price_change_pct:-10,market_pct:-20,st_pct:-11,market_excess_pp:10,st_excess_pp:1,gap:null,alternative_actual_anchor:null}
const rows=[['603398','沐邦'],['002514','宝馨'],['600363','联光'],['002667','威领'],['688053','思科瑞']].map(([symbol,name])=>({symbol,name,scope:symbol==='688053'?'longitudinal_star':symbol==='600363'?'entrant_main_board':'fixed_main_board',calendar_days:126,traded_days:symbol==='002667'?123:126,factor_change_dates:[],raw_qfq_differ_days:0,gaps:[],channels:[],windows:{all:w,'5':{...w,anchor:'2026-10-30',market_days:5,stock_pct:10},'20':symbol==='002667'?{...w,anchor:'2026-10-09',market_days:20,stock_pct:null,market_excess_pp:null,st_excess_pp:null,reference_price_change_pct:13.925,gap:'共同日期起点没有实际成交',alternative_actual_anchor:{anchor:'2026-09-29',through:'2026-11-06',market_days:23,actual_trading_days:20,stock_pct:13.925,market_pct:-9.46,st_pct:-9.79,not_same_window:true}}:{...w,anchor:'2026-10-09',market_days:20}}}))
const data:RegimeStockPriceCheck={start:'2026-05-06',through:'2026-11-06',subjects:5,unique_trade_dates:626,quote_points:2001,valid_responses:16,all_available_prices_agree:true,recent_five_up:5,recent_twenty_down:4,recent_twenty_unavailable:1,boundary:'跨渠道不证明底层独立。',failed_requests:[{symbol:'603398',key:'eastmoney_raw',error:'断开'}],rows}
afterEach(cleanup)
it('共同日期缺成交端点留空，另起实际日期的窗口明确标23日',()=>{
 render(<STStockPriceCrosscheck data={data}/>);
 expect(screen.getByText('无成交端点')).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:'威领 · 002667'}))
 expect(screen.getByLabelText('价格交叉核对公司')).toHaveValue('002667')
 expect(screen.getByText(/这跨23个市场交易日、其中20个个股成交日/)).toBeVisible()
 expect(screen.getByText(/按原参考价计算的变化为\+13.93%/)).toBeVisible()
})
it('科创范围不混入主板，也不路由到未覆盖的公告面板',()=>{
 const fn=vi.fn();render(<STStockPriceCrosscheck data={data} onCompany={fn}/>);
 fireEvent.click(screen.getByRole('button',{name:'思科瑞 · 688053'}))
 expect(screen.getByText('科创板纵向跟踪，不入主板样本')).toBeVisible()
 expect(screen.queryByRole('button',{name:/接着看思科瑞/})).not.toBeInTheDocument()
 fireEvent.change(screen.getByLabelText('价格交叉核对公司'),{target:{value:'002514'}})
 fireEvent.click(screen.getByRole('button',{name:'接着看宝馨的已核公告时间线 →'}));expect(fn).toHaveBeenCalledWith('002514')
})
it('价格冲突时改变阅读结论，缺数据不伪造已核实',()=>{
 const {rerender}=render(<STStockPriceCrosscheck data={{...data,all_available_prices_agree:false}}/>);
 expect(screen.getByRole('heading',{name:'行情渠道存在差异，先核对再解释'})).toBeVisible()
 rerender(<STStockPriceCrosscheck data={null}/>);expect(screen.queryByRole('region',{name:'五股行情与窗口核对'})).not.toBeInTheDocument()
})
it('停复牌原件按已知时点展开，后来控制权事件不倒填',()=>{
 const source={title:'结果暨复牌原件',url:'https://example.com/resume.pdf#page=3',page:3,sha256:'a'.repeat(64)}
 const halt={symbol:'002667',cause:'要约期限届满，结果需进一步确认',cause_key:'offer_result_confirmation',start:'2026-09-30',resume:'2026-10-12',halt_disclosed_on:'2026-09-30',resume_disclosed_on:'2026-10-12',new_primary_documents:2,answer:'先待结果，后来达到最低生效条件并复牌，当时控制权未变。',boundary:'不把三日当三个案例。',market_halt_dates:['2026-09-30','2026-10-08','2026-10-09'],market_halt_days:3,previous_actual_close_date:'2026-09-29',first_actual_resume_date:'2026-10-12',schedule_matches_quotes:true,continuous_episode_count:1,facts:[{published_on:'2026-10-12',signed_on:'2026-10-12',text:'6.12%达到5.00%最低条件，原定30.00%不等于已得比例。',source}],later_verified_event:{id:'later',published_on:'2026-11-06',text:'后来出现新的控制权文件。',source,reused_existing_event:true}}
 const revised={...data,rows:data.rows.map(r=>r.symbol==='002667'?{...r,halt_evidence:halt}:r)}
 render(<STStockPriceCrosscheck data={revised}/>);fireEvent.click(screen.getByRole('button',{name:'威领 · 002667'}))
 expect(screen.getByText('先待结果，后来达到最低生效条件并复牌，当时控制权未变。')).toBeVisible()
 expect(screen.getByText('6.12%达到5.00%最低条件，原定30.00%不等于已得比例。')).not.toBeVisible()
 fireEvent.click(screen.getByText('展开正式停复牌安排与当时已知'))
 expect(screen.getByRole('link',{name:'结果暨复牌原件 · 第3页 ↗'})).toHaveAttribute('href',source.url)
 expect(screen.getByText(/2026-11-06的既有已核事件/)).toBeVisible()
 expect(screen.getByText(/本轮此公司新核2份原件，其余沿用既有证据/)).toBeVisible()
})
