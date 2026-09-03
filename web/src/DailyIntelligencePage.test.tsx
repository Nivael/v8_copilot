import {render,screen} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {DailyIntelligencePage} from './DailyIntelligencePage'

describe('DailyIntelligencePage',()=>{
  afterEach(()=>vi.restoreAllMocks())

  it('keeps the frozen section order and labels shadow as non-trading research',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({
      contract_version:'p7_daily_intelligence_v1',as_of:'2026-09-03',
      checked_through:{market_activity:'2026-09-03',announcements:'2026-09-03',linkage:'2026-09-03'},
      release_status:{p7a_announcements:'descriptive',p7b_activity:'shadow',p7c_linkage:'shadow'},
      coverage:{membership_count:203,activity_row_count:203,turnover_rate_f_coverage:.99,full_universe_ready:true},
      hard_transitions:[],priority_announcements:[{bundle_id:'B1',symbol:'002528',titles:['预重整债权申报公告'],priority_reasons:['may_change_research_judgment'],announcement_ids:['A1'],conflict_status:'clear',source_urls:[]}],
      activity_anomalies:[{anomaly_id:'X1',symbol:'000610',turnover_rate_f:9.1,narrative:'异常交易活跃描述',history_count:83,turnover_percentile_120:97.6,turnover_robust_z_120:5.8}],
      research_queue:[{item_id:'Q1',priority:'monitor',symbol:'000610',relation:'activity_without_announcement',reasons:['先排查信息缺口'],first_check:'检查正式公告'}],
      continuing_watch:[{episode_id:'E1',symbol:'000911',last_hit_date:'2026-09-02',reason:'仍在观察窗',next_check:'检查新正式公告'}],
      overflow_count:0,
      risk_notice:'异常量价只表示相对历史的交易活跃变化，不证明资金主体、方向、内幕信息或未来收益。',
    }),{status:200}))

    render(<DailyIntelligencePage/>)
    const headings=await screen.findAllByRole('heading',{level:2})
    expect(headings.map(item=>item.textContent)).toEqual([
      '硬状态变化','重点公告','异常交易活跃','联动研究队列','持续观察',
    ])
    expect(screen.getAllByText('影子观察')).toHaveLength(2)
    expect(screen.getByText(/不证明资金主体/)).toBeInTheDocument()
    expect(screen.getByText(/先排查信息缺口/)).toBeInTheDocument()
  })
})
