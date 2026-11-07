import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {MemoryRouter} from 'react-router-dom'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {App} from './App'

describe('App',()=>{
  afterEach(()=>{cleanup();vi.restoreAllMocks()})

  it('opens the market reading with exactly two primary tabs and no research composer',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({availability:'warming',refresh:{in_progress:false,last_error:null}}),{status:200}))
    render(<MemoryRouter initialEntries={['/']}><App/></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'市场判断',level:1})).toBeInTheDocument()
    const nav=document.querySelector('nav')!
    expect(Array.from(nav.querySelectorAll('a')).map(a=>a.textContent)).toEqual(['市场判断','跟踪与经验'])
    expect(screen.queryByRole('textbox',{name:'研究问题'})).not.toBeInTheDocument()
    expect(screen.queryByRole('link',{name:/研究问答/})).not.toBeInTheDocument()
    expect(vi.mocked(fetch).mock.calls.every(([url])=>String(url).includes('/workbench/market'))).toBe(true)
  })

  it('keeps a submitted compatibility question and its completed answer on the legacy page',async()=>{
    const answer='当前快照没有该股票的可复算价格窗口。'
    const response={
      contract_version:'v8_copilot_api_contract_v2',route:{route:'answer_query'},interpretation:{},
      answer_card:{
        question:'最近股价和换手率怎样？',object_ref:'stock:000033',view:'query',as_of:'2026-06-01',
        sample_scope:'合成行情覆盖测试',evidence_grade:'descriptive_query',lens_invocations:[],
        lens_gap:[{gap_id:'stock_price_coverage',missing_for:'前复权价格窗口',note:answer}],
        source_freshness:{status:'2026-06-01'},body_rows:[{row_id:'status',状态:'历史状态记录'}],
        analysis_claims:[],data_debt:[],data_debt_refs:[],caveats:[],provenance:['synthetic:status'],
      },claims:[],gaps:[],sedimentation_candidates:[],degraded:false,
      degraded_reasons:[],llm_used:false,query_template_id:null,question_cards:[],
      data_debt_candidates:[],navigation_refs:[],
      narrative:{direct_answer:{text:answer,backing:[]},reasoning_steps:[],
        uncertainties:[],watch_items:[],basis_note:'合成测试的行情覆盖缺口。'},
    }
    const stream={request_id:'compatibility-test',sequence:1,event:'completed',payload:{response}}
    const fetchMock=vi.spyOn(globalThis,'fetch').mockImplementation(async input=>
      String(input).includes('/answers/stream')
        ?new Response(`${JSON.stringify(stream)}\n`,{status:200,headers:{'Content-Type':'application/x-ndjson'}})
        :new Response(JSON.stringify({availability:'warming',refresh:{in_progress:false,last_error:null}}),{status:200}))
    render(<MemoryRouter initialEntries={['/legacy?symbol=000033']}><App/></MemoryRouter>)
    const composer=await screen.findByRole('textbox',{name:'研究问题'})
    fireEvent.change(composer,{target:{value:'最近股价和换手率怎样？'}})
    fireEvent.click(screen.getByRole('button',{name:'提交'}))

    expect(await screen.findByText(answer)).toBeInTheDocument()
    expect(screen.getByRole('textbox',{name:'研究问题'})).toHaveValue('最近股价和换手率怎样？')
    expect(screen.queryByRole('heading',{name:'市场判断',level:1})).not.toBeInTheDocument()
    expect(fetchMock.mock.calls).toHaveLength(1)
    const request=JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
    expect(request.object).toEqual({kind:'stock',ref:'000033'})
    expect(Array.from(document.querySelectorAll('nav a')).map(a=>a.textContent)).toEqual(['市场判断','跟踪与经验'])
  })

  it('resolves a non-episode announcement deep link into a dossier detail focus',async()=>{
    vi.spyOn(globalThis,'fetch').mockImplementation(async input=>String(input).includes('market-risk')?new Response('',{status:503}):new Response(JSON.stringify({
      symbol:'603398',display_name:'沐邦高科',as_of:'2026-01-02',
      price_series:[{date:'2026-01-02',close:13.5}],status_intervals:[],events:[{
        event_id:'announcement:1',date:'2026-01-01',title:'正式公告',
        episode_type:'other_event_path',episode_label:'公开公告（未纳入事件段）',
        subtype_label:'其他公开公告',timeline_lane:'financial',timeline_label:'财报与公告',
        provenance_refs:['announcement:1'],related_lens_ids:[],
      }],
      timeline_lanes:[{lane_id:'financial',label:'财报与公告',event_ids:[]}],
      lens_summaries:[],data_gaps:[],display_labels:{},provenance:[],
    }),{status:200,headers:{'Content-Type':'application/json'}}))
    render(<MemoryRouter initialEntries={[
      '/stocks/603398?event=announcement%3A1&date=2026-01-01&title=虚构公告',
    ]}><App/></MemoryRouter>)

    expect(await screen.findByRole('heading',{name:'正式公告'})).toBeInTheDocument()
    expect(screen.queryByText('虚构公告')).not.toBeInTheDocument()
    expect(screen.getByText('公开公告（未纳入事件段）')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'就此提问'}).getAttribute('href')).toContain('object_kind=stock_event')
    expect(screen.getByRole('button',{name:'1年'})).toHaveAttribute('aria-pressed','true')
    expect(screen.getByRole('checkbox',{name:'仅重点节点'})).toBeChecked()
    fireEvent.click(screen.getByRole('button',{name:'3月'}))
    expect(screen.getByRole('button',{name:'3月'})).toHaveAttribute('aria-pressed','true')
    expect(screen.getByRole('button',{name:'财报与公告'})).toHaveAttribute('aria-pressed','false')
    fireEvent.click(screen.getByRole('button',{name:'财报与公告'}))
    expect(screen.getByRole('button',{name:'财报与公告'})).toHaveAttribute('aria-pressed','true')
  })

  it('keeps announcements newer than the price snapshot visible and separated',async()=>{
    vi.spyOn(globalThis,'fetch').mockImplementation(async input=>String(input).includes('market-risk')?new Response('',{status:503}):new Response(JSON.stringify({
      symbol:'300123',display_name:'ST亚光',as_of:'2026-06-26',
      price_series:[{date:'2026-06-26',close:6.2}],status_intervals:[],events:[{
        event_id:'announcement:1225415538',date:'2026-07-08',title:'关于公开招募和遴选重整投资人的公告',
        episode_type:'other_event_path',episode_label:'正式公告（尚未纳入 M6 事件段）',
        subtype:'announcement_unclassified',subtype_label:'正式公告，尚未分类',timeline_lane:'restructuring',
        timeline_label:'重整与预重整（公告标题辅助分组）',provenance_refs:['announcement:1225415538'],related_lens_ids:[],
      }],
      timeline_lanes:[{lane_id:'restructuring',label:'重整与预重整',event_ids:['announcement:1225415538']}],
      lens_summaries:[],data_gaps:[],display_labels:{
        event_count:'1 条正式公告 · 0 个 M6 已分类节点',price_data_as_of:'2026-06-26',
        announcement_data_as_of:'2026-07-08',announcement_refresh_checked_at:'2026-07-12',episode_index_as_of:'2026-07-07',
      },provenance:[],
    }),{status:200,headers:{'Content-Type':'application/json'}}))
    render(<MemoryRouter initialEntries={['/stocks/300123']}><App/></MemoryRouter>)

    expect(await screen.findByRole('region',{name:'价格截止后公告'})).toBeInTheDocument()
    expect(screen.getByText('晚于 2026-06-26，不能与同期价格联读')).toBeInTheDocument()
    expect(screen.getByRole('button',{name:/2026-07-08.*公开招募和遴选重整投资人/})).toBeInTheDocument()
  })
})
