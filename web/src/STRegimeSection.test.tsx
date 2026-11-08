import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {STRegimeSection} from './STRegimeSection'
import {buildRegimeStory} from './stRegimeStory'
import type {RegimeFixed,RegimePeriod,STRegimeData} from './stRegimeTypes'

function fixture():STRegimeData{
  const period:RegimePeriod={start:'2026-05-08',through:'2026-07-03',days:40,complete:true,reference_change_pct:-10,market_change_pct:-2,small_cap_change_pct:-4,daily_volatility_pct:1.5,mean_absolute_move_pct:1,max_drawdown_pct:-11,mean_positive_breadth_pct:43,mean_dispersion_pp:7.8,beyond_old_down_pct:0,beyond_old_up_pct:0,minimum_coverage_pct:98,member_observations:100,trading_observations:98,suspended_observations:2,missing_observations:0,terminal_exclusions:0,relation:{days:40,correlation:.05,beta:.05,r_squared:.0025},conditions:[{key:'up',label:'大盘上涨日',days:20,market_mean_pct:1,st_mean_pct:.5,mean_excess_pp:-.5,positive_breadth_pct:60},{key:'down',label:'大盘下跌日',days:20,market_mean_pct:-1,st_mean_pct:-.8,mean_excess_pp:.2,positive_breadth_pct:35},{key:'stress',label:'大盘跌超1%日',days:10,market_mean_pct:-2,st_mean_pct:-1,mean_excess_pp:1,positive_breadth_pct:33}]}
  const stock={symbol:'600001',name:'ST测试甲',venue:'上海',risk_label_at_anchor:'ST',still_st_at_end:true,return_pct:10,market_excess_pp:12,missing_quote_days:0,consistency_days:40,consistency_mismatches:0,gap:null}
  const fixed:RegimeFixed={anchor:'2026-07-03',through:'2026-08-28',total:3,covered:2,missing:1,median_pct:0,p10_pct:-8,p90_pct:8,positive_pct:50,note:'固定名单，保留缺价者；不是实际成交收益。',rows:[stock,{...stock,symbol:'000001',name:'ST测试乙',venue:'深圳',still_st_at_end:false,return_pct:-10,market_excess_pp:-8},{...stock,symbol:'000002',name:'ST缺价样本',venue:'深圳',return_pct:null,market_excess_pp:null,gap:'起止收盘缺价；未填零或沿用最后报价',missing_quote_days:3}]}
  return {availability:'available',version:'test',rule_day:'2026-07-06',announcement_day:'2026-04-24',start:'2026-05-06',through:'2026-09-03',generated_at:'2026-11-08T00:00:00Z',content_digest:'abc123',input_digest:'def',source_asset:'test',processor_sha256:'test',comparisons:['40','20','all'].map(key=>({key,label:key==='all'?'完整已覆盖后窗':`前后各${key}个交易日`,before:{...period,days:key==='20'?20:40},after:{...period,start:'2026-07-06',through:key==='20'?'2026-07-31':'2026-08-28',days:key==='all'?44:Number(key),reference_change_pct:key==='20'?-8:.5,relation:{...period.relation,correlation:.46}},fixed_before:fixed,fixed_after:fixed,paired:{count:2,symbols:['600001','000001'],before_median_pct:-10,after_median_pct:0}})),daily:[{date:'2026-07-03',anchor:'2026-07-02',return_pct:1,market_pct:2,small_cap_pct:2,member_count:3,observed_count:2,coverage_pct:66,suspended:['000002'],missing:[],positive_pct:50,dispersion_pp:5,beyond_old_down_pct:0,beyond_old_up_pct:0},{date:'2026-07-06',anchor:'2026-07-03',return_pct:-2,market_pct:-1,small_cap_pct:-1,member_count:3,observed_count:2,coverage_pct:66,suspended:['000002'],missing:[],positive_pct:50,dispersion_pp:5,beyond_old_down_pct:3,beyond_old_up_pct:3}],path:[{date:'2026-07-02',st:100,market:100,small:100},{date:'2026-07-03',st:101,market:102,small:102},{date:'2026-07-06',st:99,market:101,small:101}],universe:{anchor_members:3,endpoint_members:2,entrants:[],exits:['000001'],distinct_main_board_members:3,excluded_board_member_days:2},limitations:['完整名单截至9月3日，近期数据待补。'],sources:[{label:'交易所规则',url:'https://www.sse.com.cn/example'}]}
}
async function openEvidence(){
 await screen.findByRole('navigation',{name:'复盘问题'})
 fireEvent.click(screen.getByText('数据、图表与全部样本'))
}
const success=(data=fixture())=>vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({availability:'available',data})}))
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

describe('ST横向复盘',()=>{
 it('按问题进入，默认完整后窗，证据保持可展开',async()=>{
  success();render(<STRegimeSection/>);
  await screen.findByRole('navigation',{name:'复盘问题'})
  expect(screen.getByRole('button',{name:/这几个月发生了什么/})).toHaveAttribute('aria-pressed','true')
  expect(screen.getByText('数据、图表与全部样本').closest('details')).not.toHaveAttribute('open')
  expect(screen.getByRole('region',{name:'前后窗口比较表'})).not.toBeVisible()
  expect(screen.getByRole('img',{name:/ST与市场同期走势/})).toBeVisible()
  await openEvidence()
  expect(screen.getByRole('combobox',{name:'ST前后比较窗口'})).toHaveValue('all')
  expect(screen.getByRole('heading',{name:'整体接近持平，个股涨跌仍明显分化'})).toBeVisible()
  expect(screen.getByText(/完整横截面截至 2026-09-03/)).toBeVisible()
  expect(screen.getByRole('img',{name:/主板ST、全市场与小盘风格/})).toBeInTheDocument()
 })
 it('切换窗口，并明确提示非等长的完整后窗',async()=>{
  success();render(<STRegimeSection/>);await openEvidence()
  fireEvent.change(screen.getByLabelText('ST前后比较窗口'),{target:{value:'20'}})
  expect(screen.getByText('整体参考下跌，本窗没有出现普涨')).toBeVisible()
  fireEvent.change(screen.getByLabelText('ST前后比较窗口'),{target:{value:'all'}})
  expect(screen.getByText(/^本项前窗40日、后窗44日，时长不同/)).toBeVisible()
 })
 it('按市场环境展示观察天数，而非宣称大盘因果贡献',async()=>{
  success();render(<STRegimeSection/>);await openEvidence()
  fireEvent.click(screen.getByRole('button',{name:'大盘联动'}))
  expect(screen.getByRole('img',{name:/逐日涨跌散点/})).toBeInTheDocument()
  expect(screen.getByText(/不能据此把跌幅分摊给大盘/)).toBeVisible()
  expect(within(screen.getByRole('region',{name:'不同大盘环境下的ST表现'})).getAllByText('大盘跌超1%日')).toHaveLength(2)
 })
 it('固定名单保留缺价和移出者，支持搜索与筛选',async()=>{
  success();render(<STRegimeSection/>);await openEvidence()
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
  success();render(<STRegimeSection/>);await openEvidence()
  fireEvent.change(screen.getByLabelText('ST横向曲线范围'),{target:{value:'all'}})
  fireEvent.click(screen.getByRole('button',{name:/2026年7月6日：/}))
  expect(screen.getByText(/4月24日已经公布/)).toBeVisible()
 })
 it('读取失败时不把缺失当成零；允许重新读取',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce({ok:false}).mockResolvedValueOnce({ok:true,json:async()=>({availability:'available',data:fixture()})}))
  render(<STRegimeSection/>);expect(await screen.findByRole('alert')).toHaveTextContent('读取失败')
  fireEvent.click(screen.getByRole('button',{name:'重读已核快照'}))
  await openEvidence()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
 })
 it('来源与分母可展开，重读只访问快照API',async()=>{
  success();render(<STRegimeSection/>);await openEvidence()
  fireEvent.click(screen.getByText('名单、分母、来源和更新限制'))
  expect(within(screen.getByText('名单、分母、来源和更新限制').closest('details')!).getByRole('link',{name:'交易所规则 ↗'})).toHaveAttribute('href','https://www.sse.com.cn/example')
  expect(screen.getByText(/重读快照不会采集新行情/)).toBeVisible()
  await act(async()=>fireEvent.click(screen.getByRole('button',{name:'重读已核快照'})))
  await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2))
  expect(fetch).toHaveBeenLastCalledWith('/api/v1/workbench/st-regime',expect.objectContaining({cache:'no-store'}))
 })
})


describe('报道与证据绑定',()=>{
 it('正文讲清名单、涨跌家数和缺失，不虚构采访',()=>{
  const data=fixture(),story=buildRegimeStory(data,data.comparisons[0])
  expect(story.lead.join('')).toContain('2只股票中，1只上涨，1只没有上涨')
  expect(story.lead.join('')).toContain('另有1只缺价或复权待核')
  expect(story.sections[0].paragraphs.join('')).toContain('前20个交易日')
  expect(story.sections[0].paragraphs.join('')).toContain('下跌8.00%')
  expect(JSON.stringify(story)).not.toMatch(/接受采访|记者获悉|消息人士|分析师表示/)
 })
 it('数据转为下跌时，标题与叙事同步改变',()=>{
  const data=fixture(),comparison=structuredClone(data.comparisons[0])
  comparison.after.reference_change_pct=-15
  comparison.before.reference_change_pct=5
  const story=buildRegimeStory(data,comparison)
  expect(story.title).toBe('涨跌幅放开，ST仍未走出下跌')
  expect(story.sections[0].heading).toBe('新规前后，市场经历了什么')
  expect(story.sections[0].paragraphs.join('')).not.toContain('调整在新规生效前就已出现')
 })
 it('无可比样本时不写成零收益或普涨',()=>{
  const data=fixture(),comparison=structuredClone(data.comparisons[0])
  comparison.fixed_after={...comparison.fixed_after,covered:0,missing:3,positive_pct:null,median_pct:null,p10_pct:null,p90_pct:null,rows:comparison.fixed_after.rows.map(row=>({...row,return_pct:null}))}
  const story=buildRegimeStory(data,comparison)
  expect(story.lead.join('')).toContain('暂时不能判断有多少股票')
  expect(story.sections[2].paragraphs[0]).toContain('没有可比的起止价格')
 })
 it('读者点正文证据链接后，打开相应的明细视角',async()=>{
  success();render(<STRegimeSection/>);await screen.findByRole('navigation',{name:'复盘问题'})
  fireEvent.click(screen.getByRole('button',{name:/下次怎样看得更准/}))
  fireEvent.click(screen.getByRole('button',{name:'查看150只完整名单 →'}))
  expect(screen.getByRole('region',{name:'固定名单全部个股表现'})).toBeVisible()
  expect(screen.getByRole('button',{name:'整批个股'})).toHaveAttribute('aria-pressed','true')
 })
 it('行情转为上涨时，不沿用下跌与修复的叙述',()=>{
  const data=fixture(),comparison=structuredClone(data.comparisons[0])
  comparison.after.reference_change_pct=8
  comparison.after.market_change_pct=3
  comparison.before.reference_change_pct=5
  comparison.before.market_change_pct=10
  data.comparisons.find(c=>c.key==='20')!.after.reference_change_pct=2
  const story=buildRegimeStory(data,comparison)
  const text=JSON.stringify(story)
  expect(story.title).toBe('ST整体参考上涨，个股的表现如何？')
  expect(text).not.toMatch(/开局仍偏弱|这段时间更抗跌|当时的跌幅已经大于大盘/)
 })

 it('短窗多数下跌时，导语不把走势称作回稳',()=>{
  const data=fixture(),comparison=structuredClone(data.comparisons.find(c=>c.key==='20')!)
  comparison.fixed_after.positive_pct=0
  comparison.fixed_after.rows[0].return_pct=-2
  const story=buildRegimeStory(data,comparison)
  expect(story.lead.join('')).not.toMatch(/回稳|另一面/)
  expect(story.lead.join('')).toContain('调整的覆盖面也很清楚')
 })

})


describe('按问题阅读与公告覆盖边界',()=>{
 it('分主题呈现，切换不要求先展开全文，缺正文不猜事实',async()=>{
  success();render(<STRegimeSection/>);await screen.findByRole('navigation',{name:'复盘问题'})
  fireEvent.click(screen.getByRole('button',{name:/公告到底改变了什么/}))
  expect(screen.getByText('本版尚未绑定公告正文选样；不以标题代替事实。')).toBeVisible()
  expect(screen.getByText('数据、图表与全部样本').closest('details')).not.toHaveAttribute('open')
  fireEvent.click(screen.getByRole('button',{name:/大盘影响有多明显/}))
  expect(screen.getByRole('region',{name:'大盘波动较大交易日'})).toBeVisible()
 })
 it('公告切公司与窗口，原件可展开，窗口不足保留待核',async()=>{
  const data=fixture()
  const e={id:'verified',symbol:'603398',name:'ST测试公司',title:'受理仍需核实回款',published_on:'2026-11-04',change:'法院受理，尚未到账。',evidence_detail:'已核原件明确受理状态。',interpretation:'受理不证明胜诉。',watch:'下一次核回款凭据。',entity_scope:'issuer',source:{url:'https://example.com/original.pdf#page=2',title:'诉讼进展公告',page:2,sha256:'filehash'},observation:{anchor:'2026-11-04',not_earliest_reaction:true,windows:{'1':{through:'2026-11-05',stock_pct:2,market_pct:1,st_pct:-1,gap:null},'5':{through:null,stock_pct:null,market_pct:null,st_pct:null,gap:'起止缺价或后续交易日不足，未填零'},'20':{through:null,stock_pct:null,market_pct:null,st_pct:null,gap:'窗口未满'}}}}
  data.themes={months:[],market_days:[],announcements:{from:'2026-07-01',through:'2026-11-06',companies:156,catalog_rows:5632,catalog_pages:210,verified_events:[e],verified_companies:1,verified_documents:1,body_reads_this_refresh:0,boundary:'正文选样不能代表全体公告。'}}
  success(data);render(<STRegimeSection/>);await screen.findByRole('navigation',{name:'复盘问题'})
  fireEvent.click(screen.getByRole('button',{name:/公告到底改变了什么/}))
  expect(screen.getByText(/正文来自此前已核材料/)).toBeVisible()
  expect(screen.getByText(/后续交易日不足，未填零/)).toBeVisible()
  fireEvent.change(screen.getByLabelText('公告后观察窗口'),{target:{value:'1'}})
  expect(screen.getByText('+2.00%')).toBeVisible()
  fireEvent.click(screen.getByText('查看依据与下一步核对'))
  expect(screen.getByRole('link',{name:/诉讼进展公告/})).toHaveAttribute('href',e.source.url)
 })
 it('缺少可比个股时不把上涨覆盖面写成零',async()=>{
  const data=fixture(),all=data.comparisons.find(c=>c.key==='all')!
  all.fixed_after={...all.fixed_after,covered:0,missing:3,positive_pct:null,median_pct:null}
  success(data);render(<STRegimeSection/>);await screen.findByRole('navigation',{name:'复盘问题'})
  expect(screen.getByText(/上涨覆盖面待核/)).toBeVisible()
  expect(screen.queryByText(/约0%上涨/)).not.toBeInTheDocument()
 })
})

it('同一事项多个视角只展示一次行情窗口，保留各页来源与记录计数',async()=>{
 const data=fixture(),source={url:'https://example.com/agreement.pdf#page=39',title:'投资协议',page:39,sha256:'samefile'}
 const e={id:'investment',event_key:'unique-event-key',source_record_count:2,symbol:'002856',name:'ST测试公司',title:'投资协议的签约与定价',published_on:'2026-09-23',change:'已签约，定价有约束。',interpretation:'余款有条件，不是市场保底。',watch:'继续核履约。',evidence_detail:'两处页码分别保留。',entity_scope:'issuer',source,source_records:[{title:'签约',change:'保证金已缴',source:{...source,page:38,url:'https://example.com/agreement.pdf#page=38'}},{title:'定价',change:'价格受协议约束',source}],observation:{anchor:'2026-09-23',not_earliest_reaction:true,windows:{'5':{through:'2026-09-30',stock_pct:1,market_pct:-1,st_pct:0,gap:null}}}}
 data.themes={months:[],market_days:[],announcements:{from:'2026-07-01',through:'2026-11-06',companies:156,catalog_rows:5632,catalog_pages:210,verified_events:[e],raw_fact_records:2,deduplicated_event_count:1,coalesced_records:1,verified_companies:1,verified_documents:1,body_reads_this_refresh:0,boundary:'记录数不是独立验证次数。'}}
 success(data);render(<STRegimeSection/>);await screen.findByRole('navigation',{name:'复盘问题'});fireEvent.click(screen.getByRole('button',{name:/公告到底改变了什么/}))
 expect(screen.getByText(/1个去重事项（2条事实记录）/)).toBeVisible()
 expect(screen.getAllByRole('heading',{name:'投资协议的签约与定价'})).toHaveLength(1)
 expect(screen.getByText(/同一事项保留2个视角、2条原记录，行情窗口只观察一次/)).toBeVisible()
 fireEvent.click(screen.getByText('查看依据与下一步核对'))
 expect(screen.getByRole('link',{name:'投资协议 · 第38页 ↗'})).toHaveAttribute('href','https://example.com/agreement.pdf#page=38')
 expect(screen.getByRole('link',{name:'投资协议 · 第39页 ↗'})).toHaveAttribute('href',source.url)
})
