import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {STRegimeSection} from './STRegimeSection'
import type {RegimeFixed,RegimePeriod,STRegimeData} from './stRegimeTypes'

function fixture():STRegimeData{
  const period:RegimePeriod={start:'2026-05-08',through:'2026-07-03',days:40,complete:true,reference_change_pct:-10,market_change_pct:-2,small_cap_change_pct:-4,daily_volatility_pct:1.5,mean_absolute_move_pct:1,max_drawdown_pct:-11,mean_positive_breadth_pct:43,mean_dispersion_pp:7.8,beyond_old_down_pct:0,beyond_old_up_pct:0,minimum_coverage_pct:98,member_observations:100,trading_observations:98,suspended_observations:2,missing_observations:0,terminal_exclusions:0,relation:{days:40,correlation:.05,beta:.05,r_squared:.0025},conditions:[{key:'up',label:'大盘上涨日',days:20,market_mean_pct:1,st_mean_pct:.5,mean_excess_pp:-.5,positive_breadth_pct:60},{key:'down',label:'大盘下跌日',days:20,market_mean_pct:-1,st_mean_pct:-.8,mean_excess_pp:.2,positive_breadth_pct:35},{key:'stress',label:'大盘跌超1%日',days:10,market_mean_pct:-2,st_mean_pct:-1,mean_excess_pp:1,positive_breadth_pct:33}]}
  const stock={symbol:'600001',name:'ST测试甲',venue:'上海',risk_label_at_anchor:'ST',still_st_at_end:true,return_pct:10,market_excess_pp:12,missing_quote_days:0,consistency_days:40,consistency_mismatches:0,gap:null}
  const fixed:RegimeFixed={anchor:'2026-07-03',through:'2026-08-28',total:3,covered:2,missing:1,median_pct:0,p10_pct:-8,p90_pct:8,positive_pct:50,note:'固定名单，保留缺价者；不是实际成交收益。',rows:[stock,{...stock,symbol:'000001',name:'ST测试乙',venue:'深圳',still_st_at_end:false,return_pct:-10,market_excess_pp:-8},{...stock,symbol:'000002',name:'ST缺价样本',venue:'深圳',return_pct:null,market_excess_pp:null,gap:'起止收盘缺价；未填零或沿用最后报价',missing_quote_days:3}]}
  return {availability:'available',version:'test',rule_day:'2026-07-06',announcement_day:'2026-04-24',start:'2026-05-06',through:'2026-09-03',generated_at:'2026-11-08T00:00:00Z',content_digest:'abc123',input_digest:'def',source_asset:'test',processor_sha256:'test',comparisons:['40','20','all'].map(key=>({key,label:key==='all'?'完整已覆盖后窗':`前后各${key}个交易日`,before:{...period,days:key==='20'?20:40},after:{...period,start:'2026-07-06',through:key==='20'?'2026-07-31':'2026-08-28',days:key==='all'?44:Number(key),reference_change_pct:key==='20'?-8:.5,relation:{...period.relation,correlation:.46}},fixed_before:fixed,fixed_after:fixed,paired:{count:2,symbols:['600001','000001'],before_median_pct:-10,after_median_pct:0}})),daily:[{date:'2026-07-03',anchor:'2026-07-02',return_pct:1,market_pct:2,small_cap_pct:2,member_count:3,observed_count:2,coverage_pct:66,suspended:['000002'],missing:[],positive_pct:50,dispersion_pp:5,beyond_old_down_pct:0,beyond_old_up_pct:0},{date:'2026-07-06',anchor:'2026-07-03',return_pct:-2,market_pct:-1,small_cap_pct:-1,member_count:3,observed_count:2,coverage_pct:66,suspended:['000002'],missing:[],positive_pct:50,dispersion_pp:5,beyond_old_down_pct:3,beyond_old_up_pct:3}],path:[{date:'2026-07-02',st:100,market:100,small:100},{date:'2026-07-03',st:101,market:102,small:102},{date:'2026-07-06',st:99,market:101,small:101}],universe:{anchor_members:3,endpoint_members:2,entrants:[],exits:['000001'],distinct_main_board_members:3,excluded_board_member_days:2},limitations:['完整名单截至9月3日，近期数据待补。'],sources:[{label:'交易所规则',url:'https://www.sse.com.cn/example'}]}
}
const success=(data=fixture())=>vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({availability:'available',data})}))
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

describe('ST横向复盘',()=>{
 it('先展示横向入口、日期边界与等长40日比较',async()=>{
  success();render(<STRegimeSection/>);
  await screen.findByText(/完整横截面截至 2026-09-03/)
  expect(screen.getByRole('combobox',{name:'ST前后比较窗口'})).toHaveValue('40')
  expect(screen.getByRole('heading',{name:'整体接近持平，个股涨跌仍明显分化'})).toBeVisible()
  expect(screen.getByText(/9月之后尚待补齐/)).toBeVisible()
  expect(screen.getByRole('img',{name:/主板ST、全市场与小盘风格/})).toBeInTheDocument()
 })
 it('切换窗口，并明确提示非等长的完整后窗',async()=>{
  success();render(<STRegimeSection/>);await screen.findByText(/完整横截面截至/)
  fireEvent.change(screen.getByLabelText('ST前后比较窗口'),{target:{value:'20'}})
  expect(screen.getByText('整体参考下跌，放宽限制没有带来普涨')).toBeVisible()
  fireEvent.change(screen.getByLabelText('ST前后比较窗口'),{target:{value:'all'}})
  expect(screen.getByText(/前窗40日、后窗44日，时长不同/)).toBeVisible()
 })
 it('按市场环境展示观察天数，而非宣称大盘因果贡献',async()=>{
  success();render(<STRegimeSection/>);await screen.findByText(/完整横截面截至/)
  fireEvent.click(screen.getByRole('button',{name:'大盘联动'}))
  expect(screen.getByRole('img',{name:/逐日涨跌散点/})).toBeInTheDocument()
  expect(screen.getByText(/不能据此把跌幅分摊给大盘/)).toBeVisible()
  expect(within(screen.getByRole('region',{name:'不同大盘环境下的ST表现'})).getAllByText('大盘跌超1%日')).toHaveLength(2)
 })
 it('固定名单保留缺价和移出者，支持搜索与筛选',async()=>{
  success();render(<STRegimeSection/>);await screen.findByText(/完整横截面截至/)
  fireEvent.click(screen.getByRole('button',{name:'整批个股'}))
  expect(screen.getByText('ST缺价样本')).toBeVisible()
  fireEvent.change(screen.getByLabelText('横向复盘名单范围'),{target:{value:'missing'}})
  expect(screen.getByText('ST缺价样本')).toBeVisible()
  expect(screen.queryByText('ST测试甲')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('横向复盘名单范围'),{target:{value:'left'}})
  expect(screen.getByText('ST测试乙')).toBeVisible()
  fireEvent.change(screen.getByLabelText('横向复盘查找公司'),{target:{value:'600001'}})
  expect(screen.getByText('没有符合筛选的公司。')).toBeVisible()
 })
 it('规则标记能打开生效与预期交易说明',async()=>{
  success();render(<STRegimeSection/>);await screen.findByText(/完整横截面截至/)
  fireEvent.change(screen.getByLabelText('ST横向曲线范围'),{target:{value:'all'}})
  fireEvent.click(screen.getByRole('button',{name:/2026年7月6日：/}))
  expect(screen.getByText(/4月24日已经公布/)).toBeVisible()
 })
 it('读取失败时不把缺失当成零；允许重新读取',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce({ok:false}).mockResolvedValueOnce({ok:true,json:async()=>({availability:'available',data:fixture()})}))
  render(<STRegimeSection/>);expect(await screen.findByRole('alert')).toHaveTextContent('读取失败')
  fireEvent.click(screen.getByRole('button',{name:'重读已核快照'}))
  await screen.findByText(/完整横截面截至/)
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
 })
 it('来源与分母可展开，重读只访问快照API',async()=>{
  success();render(<STRegimeSection/>);await screen.findByText(/完整横截面截至/)
  fireEvent.click(screen.getByText('名单、分母、来源和更新限制'))
  expect(screen.getByRole('link',{name:'交易所规则 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/example')
  expect(screen.getByText(/重读快照不会采集新行情/)).toBeVisible()
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'重读已核快照'})))
  await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2))
  expect(fetch).toHaveBeenLastCalledWith('/api/v1/workbench/st-regime',expect.objectContaining({cache:'no-store'}))
 })
})
